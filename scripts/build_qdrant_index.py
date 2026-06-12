#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from benchmark_utils import EventLogger
from config_utils import add_common_args, auth_headers, get_path, http_json, load_config, validate_config


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def chunk_text(text: str, target_chars: int = 1200, overlap_chars: int = 180) -> list[str]:
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= target_chars:
            current = f"{current}\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    if len(chunks) <= 1:
        return chunks
    out: list[str] = []
    prev_tail = ""
    for chunk in chunks:
        merged = f"{prev_tail}\n{chunk}".strip() if prev_tail else chunk
        out.append(merged)
        prev_tail = chunk[-overlap_chars:]
    return out


def embedding_request_shape(config: dict[str, Any], texts: list[str]) -> dict[str, Any]:
    payload = {"model": get_path(config, "embedding.model"), "input": texts}
    params = get_path(config, "embedding.params", {})
    if params:
        if not isinstance(params, dict):
            raise ValueError("embedding.params must be a mapping")
        payload.update(params)
    return payload


def embed_texts(config: dict[str, Any], texts: list[str]) -> list[list[float]]:
    url = get_path(config, "embedding.base_url").rstrip("/") + "/embeddings"
    payload = embedding_request_shape(config, texts)
    headers = auth_headers(get_path(config, "embedding.api_key"))
    resp = http_json("POST", url, payload, headers, timeout=int(get_path(config, "runtime.timeout_seconds", 120)))
    return [item["embedding"] for item in resp["data"]]


def point_id(article_id: str, chunk_index: int) -> str:
    digest = hashlib.md5(f"{article_id}:{chunk_index}".encode("utf-8")).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def collection_vector_size(info: dict[str, Any]) -> int | None:
    vectors = (
        info.get("result", {})
        .get("config", {})
        .get("params", {})
        .get("vectors")
    )
    if isinstance(vectors, dict) and isinstance(vectors.get("size"), int):
        return vectors["size"]
    if isinstance(vectors, dict):
        first_named_vector = next((value for value in vectors.values() if isinstance(value, dict)), None)
        if isinstance(first_named_vector, dict) and isinstance(first_named_vector.get("size"), int):
            return first_named_vector["size"]
    return None


def wait_for_collection_deleted(qdrant_url: str, collection: str, headers: dict[str, str], timeout_seconds: float = 30.0) -> None:
    collection_url = f"{qdrant_url}/collections/{collection}"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            http_json("GET", collection_url, None, headers)
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return
            raise
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for Qdrant collection '{collection}' to be deleted")


def ensure_collection(qdrant_url: str, collection: str, headers: dict[str, str], vector_size: int, recreate: bool) -> None:
    collection_url = f"{qdrant_url}/collections/{collection}"
    if recreate:
        deleted = False
        try:
            http_json("DELETE", collection_url, None, headers)
            print(f"deleted existing collection: {collection}")
            deleted = True
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
            print(f"collection did not exist before rebuild: {collection}")
        if deleted:
            wait_for_collection_deleted(qdrant_url, collection, headers)
    try:
        http_json("PUT", collection_url, {"vectors": {"size": vector_size, "distance": "Cosine"}}, headers)
        print(f"created collection: {collection} ({vector_size} dims)")
    except RuntimeError as exc:
        if "HTTP 409" not in str(exc):
            raise
        info = http_json("GET", collection_url, None, headers)
        existing_size = collection_vector_size(info)
        if existing_size == vector_size:
            print(f"using existing collection: {collection} ({existing_size} dims)")
            return
        raise RuntimeError(
            f"Qdrant collection '{collection}' already exists with vector size {existing_size}, "
            f"but config requires {vector_size}. Use a new qdrant.collection_name or rerun with --recreate-collection."
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Qdrant index for UC1 KB")
    add_common_args(parser)
    parser.add_argument("--data-dir", default="benchmark_data")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--recreate-collection", action="store_true", help="Delete and recreate the Qdrant collection before indexing")
    parser.add_argument("--event-log", help="Optional JSONL event log for the web UI")
    args = parser.parse_args()
    events = EventLogger(args.event_log)
    events.emit("job_started", stage="validate_dataset", message="Validate dataset / 校验数据集")

    config = load_config(args.config)
    problems = validate_config(config, allow_placeholders=args.allow_example_placeholders or args.dry_run)
    if problems:
        events.emit("stage_error", stage="validate_config", message="\n".join(problems))
        raise SystemExit("\n".join(f"CONFIG ERROR: {p}" for p in problems))

    articles = read_jsonl(ROOT / args.data_dir / "uc1" / "kb_articles.jsonl")
    events.emit("stage_done", stage="validate_dataset", total_articles=len(articles), message="Dataset ready / 数据集可用")
    events.emit("stage_started", stage="chunk_knowledge", message="Split knowledge base into chunks / 拆分知识库")
    chunks: list[dict[str, Any]] = []
    for article in articles:
        for idx, chunk in enumerate(chunk_text(article["body"])):
            chunks.append({"article": article, "chunk_index": idx, "text": chunk})
    events.emit("stage_done", stage="chunk_knowledge", total_chunks=len(chunks), message="Knowledge chunks ready / 知识片段已准备")

    if args.dry_run:
        events.emit("job_done", stage="complete", status="ok", completed=len(chunks), total=len(chunks), message="Dry run complete / 试运行完成")
        print(json.dumps({
            "mode": "dry-run",
            "articles": len(articles),
            "chunks": len(chunks),
            "sample_embedding_request": embedding_request_shape(config, [chunks[0]["text"]]),
            "qdrant_collection": get_path(config, "qdrant.collection_name"),
        }, ensure_ascii=False, indent=2))
        return 0

    qdrant_url = get_path(config, "qdrant.url").rstrip("/")
    collection = get_path(config, "qdrant.collection_name")
    qheaders = auth_headers(get_path(config, "qdrant.api_key"), get_path(config, "qdrant.username"), get_path(config, "qdrant.password"))
    vector_size = int(get_path(config, "runtime.qdrant_vector_size"))
    events.emit("stage_started", stage="prepare_collection", collection=collection, message="Prepare knowledge index / 准备知识索引")
    ensure_collection(qdrant_url, collection, qheaders, vector_size, args.recreate_collection)
    events.emit("stage_done", stage="prepare_collection", collection=collection, message="Knowledge index ready / 知识索引已就绪")

    for start in range(0, len(chunks), args.batch_size):
        batch = chunks[start:start + args.batch_size]
        events.emit("stage_started", stage="embed_batch", completed=start, total=len(chunks), message="Create vector embeddings / 生成向量")
        vectors = embed_texts(config, [row["text"] for row in batch])
        points = []
        for row, vector in zip(batch, vectors):
            article = row["article"]
            points.append({
                "id": point_id(article["article_id"], row["chunk_index"]),
                "vector": vector,
                "payload": {
                    "article_id": article["article_id"],
                    "chunk_index": row["chunk_index"],
                    "product": article["product"],
                    "category": article["category"],
                    "topic_id": article["topic_id"],
                    "title": article["title"],
                    "text": row["text"],
                    "source_ids": article["source_ids"],
                },
            })
        http_json("PUT", f"{qdrant_url}/collections/{collection}/points?wait=true", {"points": points}, qheaders)
        print(f"upserted {start + len(batch)}/{len(chunks)} chunks")
        events.emit("progress", stage="upsert_vectors", completed=start + len(batch), total=len(chunks), message="Import chunks into knowledge index / 导入知识索引")
    events.emit("job_done", stage="complete", status="ok", completed=len(chunks), total=len(chunks), message="Qdrant initialization complete / 初始化完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

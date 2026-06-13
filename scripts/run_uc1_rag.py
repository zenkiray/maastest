#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from benchmark_utils import EventLogger, call_chat_completion, parse_int_list, run_concurrency_sweep
from build_qdrant_index import embed_texts
from config_utils import add_common_args, auth_headers, get_path, http_json, load_config, validate_config


ROOT = Path(__file__).resolve().parents[1]


def preview_text(value: Any, limit: int = 1800) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def make_output_streamer(events: EventLogger, item_id: str, run_index: int, concurrency: int, stage: str):
    parts: list[str] = []
    last_emit = 0.0
    last_len = 0

    def emit(force: bool = False) -> None:
        nonlocal last_emit, last_len
        text = "".join(parts)
        now = time.time()
        if not force and now - last_emit < 0.6 and len(text) - last_len < 120:
            return
        last_emit = now
        last_len = len(text)
        events.emit(
            "model_output_delta",
            uc="uc1",
            item_id=item_id,
            run_index=run_index,
            concurrency=concurrency,
            stage=stage,
            output_preview=preview_text(text),
            output_chars=len(text),
            message="Model output streaming / 大模型输出中",
        )

    def on_delta(delta: str) -> None:
        parts.append(delta)
        emit()

    return on_delta


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def qdrant_search(config: dict[str, Any], vector: list[float], top_k: int) -> list[dict[str, Any]]:
    qdrant_url = get_path(config, "qdrant.url").rstrip("/")
    collection = get_path(config, "qdrant.collection_name")
    headers = auth_headers(get_path(config, "qdrant.api_key"), get_path(config, "qdrant.username"), get_path(config, "qdrant.password"))
    resp = http_json("POST", f"{qdrant_url}/collections/{collection}/points/search", {
        "vector": vector,
        "limit": top_k,
        "with_payload": True,
    }, headers, timeout=int(get_path(config, "runtime.timeout_seconds")))
    return resp.get("result", [])


def rerank(config: dict[str, Any], query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not get_path(config, "reranker.enabled"):
        return candidates
    url = get_path(config, "reranker.base_url").rstrip("/") + "/" + str(get_path(config, "reranker.path", "/rerank")).lstrip("/")
    docs = [c["payload"]["text"] for c in candidates]
    top_n = int(get_path(config, "runtime.rerank_top_n"))
    params = get_path(config, "reranker.params", {})
    if params and not isinstance(params, dict):
        raise ValueError("reranker.params must be a mapping")
    if get_path(config, "reranker.request_format", "openai") == "dashscope":
        payload = {
            "model": get_path(config, "reranker.model"),
            "input": {"query": query, "documents": docs},
            "parameters": {**params, "top_n": top_n},
        }
    else:
        payload = {"model": get_path(config, "reranker.model"), "query": query, "documents": docs, "top_n": top_n, **params}
    headers = auth_headers(get_path(config, "reranker.api_key"))
    resp = http_json("POST", url, payload, headers, timeout=int(get_path(config, "runtime.timeout_seconds")))
    results = resp.get("results", [])
    if not isinstance(results, list):
        results = []
    output = resp.get("output", {})
    if not results and isinstance(output, dict) and isinstance(output.get("results"), list):
        results = output["results"]
    ranked = []
    for item in results:
        idx = item.get("index")
        if isinstance(idx, int) and 0 <= idx < len(candidates):
            copy = dict(candidates[idx])
            copy["rerank_score"] = item.get("relevance_score", item.get("score"))
            ranked.append(copy)
    return ranked or candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Run UC1 RAG benchmark")
    add_common_args(parser)
    parser.add_argument("--data-dir", default="benchmark_data")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency-levels", help="Comma-separated override, for example: 1 or 1,4")
    parser.add_argument("--runs-per-platform", type=int, help="Override runtime.runs_per_platform")
    parser.add_argument("--timeout-seconds", type=int, help="Override runtime.timeout_seconds")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming chat completions for this run")
    parser.add_argument("--no-reranker", action="store_true", help="Disable reranker for this UC1 run")
    parser.add_argument("--event-log", help="Optional JSONL event log for the web UI")
    args = parser.parse_args()
    events = EventLogger(args.event_log)
    events.emit("job_started", uc="uc1", stage="load_question", message="Load FAQ questions / 读取问答问题")

    config = load_config(args.config)
    if args.timeout_seconds:
        config["runtime"]["timeout_seconds"] = args.timeout_seconds
    if args.no_stream:
        config["runtime"]["stream"] = False
    if args.no_reranker:
        config["reranker"]["enabled"] = False
    reranker_enabled = bool(get_path(config, "reranker.enabled"))
    problems = validate_config(config, allow_placeholders=args.allow_example_placeholders or args.dry_run)
    if problems:
        events.emit("stage_error", uc="uc1", stage="validate_config", message="\n".join(problems))
        raise SystemExit("\n".join(f"CONFIG ERROR: {p}" for p in problems))

    questions = read_jsonl(ROOT / args.data_dir / "uc1" / "faq_questions.jsonl")
    if args.limit:
        questions = questions[:args.limit]
    events.emit("stage_done", uc="uc1", stage="load_question", total=len(questions), message="Questions ready / 问题已准备")
    out_dir = ROOT / str(get_path(config, "runtime.output_dir")) / str(get_path(config, "runtime.platform_label", "platform")) / "uc1"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    raw_path = out_dir / f"uc1_raw_logs_{stamp}.jsonl"
    summary_path = out_dir / f"uc1_summary_{stamp}.json"

    def worker(row: dict[str, Any], run_index: int, concurrency: int) -> dict[str, Any]:
        started = time.time()
        item_id = row["question_id"]
        events.emit("request_started", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="load_question", message="Start FAQ case / 开始问答案例")
        if args.dry_run:
            dry_run_stages = [
                ("embed_query", "Embed customer question / 生成问题向量"),
                ("search_knowledge", "Search knowledge base / 检索知识库"),
            ]
            if reranker_enabled:
                dry_run_stages.append(("rank_evidence", "Rank supporting evidence / 排序证据"))
            dry_run_stages += [
                ("generate_answer", "Generate answer / 生成答复"),
                ("record_metrics", "Record benchmark metrics / 记录测试指标"),
            ]
            for stage, message in dry_run_stages:
                payload = {"output_preview": "MOCK_ANSWER: would embed query, search Qdrant, optionally rerank, then stream LLM answer."} if stage == "generate_answer" else {}
                events.emit("stage_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage=stage, message=message, **payload)
            events.emit("request_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, status="ok", stage="record_metrics", message="FAQ case complete / 问答案例完成")
            return {
                "uc": "uc1",
                "run_index": run_index,
                "concurrency": concurrency,
                "question_id": row["question_id"],
                "mode": "dry-run",
                "status": "ok",
                "retrieved": row["expected_article_ids"][: int(get_path(config, "runtime.rerank_top_n"))],
                "latency_ms": round((time.time() - started) * 1000, 2),
                "e2e_latency_ms": round((time.time() - started) * 1000, 2),
                "llm_latency_ms": 0.0,
                "e2e_ttft_ms": 0.0,
                "llm_ttft_ms": 0.0,
                "e2e_tpot_ms": 0.0,
                "llm_tpot_ms": 0.0,
                "ttft_ms": 0.0,
                "tpot_ms": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "answer": "MOCK_ANSWER: would embed query, search Qdrant, optionally rerank, then stream LLM answer.",
            }
        try:
            events.emit("stage_started", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="embed_query", message="Embed customer question / 生成问题向量")
            vector = embed_texts(config, [row["question"]])[0]
            events.emit("stage_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="embed_query")
            events.emit("stage_started", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="search_knowledge", message="Search knowledge base / 检索知识库")
            hits = qdrant_search(config, vector, int(get_path(config, "runtime.top_k")))
            events.emit("stage_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="search_knowledge", hit_count=len(hits))
            if reranker_enabled:
                events.emit("stage_started", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="rank_evidence", message="Rank supporting evidence / 排序证据")
                ranked = rerank(config, row["question"], hits)
                events.emit("stage_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="rank_evidence", hit_count=len(ranked))
            else:
                ranked = hits
            context = "\n\n".join(f"[{h['payload']['article_id']}]\n{h['payload']['text']}" for h in ranked)
            messages = [
                {"role": "system", "content": "You are a compliant CardX/AutoX banking FAQ assistant. Answer only from retrieved context. Do not ask for OTP, PIN, password, or full card number."},
                {"role": "user", "content": f"Question:\n{row['question']}\n\nRetrieved context:\n{context}"},
            ]
            events.emit("stage_started", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="generate_answer", message="Generate answer / 生成答复")
            llm_started = time.time()
            llm = call_chat_completion(config, messages, on_delta=make_output_streamer(events, item_id, run_index, concurrency, "generate_answer"))
            events.emit("stage_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="generate_answer", status=llm["status"], output_preview=preview_text(llm.get("content")))
            events.emit("stage_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="record_metrics", message="Record benchmark metrics / 记录测试指标")
            events.emit("request_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, status=llm["status"], stage="record_metrics", message="FAQ case complete / 问答案例完成")
            e2e_latency_ms = round((time.time() - started) * 1000, 2)
            local_before_llm_ms = round((llm_started - started) * 1000, 2)
            e2e_ttft_ms = None if llm["ttft_ms"] is None else round(local_before_llm_ms + float(llm["ttft_ms"]), 2)
            return {
                "uc": "uc1",
                "run_index": run_index,
                "concurrency": concurrency,
                "question_id": row["question_id"],
                "status": llm["status"],
                "error": llm["error"],
                "retrieved": [h["payload"]["article_id"] for h in ranked],
                "latency_ms": e2e_latency_ms,
                "e2e_latency_ms": e2e_latency_ms,
                "llm_latency_ms": llm["latency_ms"],
                "ttft_ms": e2e_ttft_ms,
                "e2e_ttft_ms": e2e_ttft_ms,
                "llm_ttft_ms": llm["ttft_ms"],
                "tpot_ms": llm["tpot_ms"],
                "e2e_tpot_ms": llm["tpot_ms"],
                "llm_tpot_ms": llm["tpot_ms"],
                "input_tokens": llm["input_tokens"],
                "output_tokens": llm["output_tokens"],
                "total_tokens": llm["total_tokens"],
                "answer": llm["content"],
            }
        except Exception as exc:
            events.emit("request_done", uc="uc1", item_id=item_id, run_index=run_index, concurrency=concurrency, status="error", stage="record_metrics", message=str(exc))
            return {
                "uc": "uc1",
                "run_index": run_index,
                "concurrency": concurrency,
                "question_id": row["question_id"],
                "status": "error",
                "error": str(exc),
                "latency_ms": round((time.time() - started) * 1000, 2),
            }

    levels = parse_int_list(args.concurrency_levels) if args.concurrency_levels else [int(x) for x in get_path(config, "runtime.concurrency_levels", [int(get_path(config, "runtime.concurrency", 1))])]
    runs = args.runs_per_platform if args.runs_per_platform else int(get_path(config, "runtime.runs_per_platform", 1))
    print(f"UC1 plan: questions={len(questions)}, concurrency_levels={levels}, runs={runs}, worker_requests={len(questions) * len(levels) * runs}", flush=True)
    events.emit("run_plan", uc="uc1", total_items=len(questions), concurrency_levels=levels, runs=runs, total_requests=len(questions) * len(levels) * runs)
    raw_logs, summaries = run_concurrency_sweep(questions, levels, runs, worker)
    with raw_path.open("w", encoding="utf-8") as f:
        for row in raw_logs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary_path.write_text(json.dumps({"uc": "uc1", "summaries": summaries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    events.emit("job_done", uc="uc1", stage="report", status="ok", raw_log_path=str(raw_path), summary_path=str(summary_path), message="UC1 report ready / UC1 报告已生成")
    print(raw_path)
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

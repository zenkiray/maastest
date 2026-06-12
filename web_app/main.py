from __future__ import annotations

import base64
import json
import hmac
import hashlib
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web_app.i18n import language_options, pick_text, request_lang, translate

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
CONFIG_DIR = ROOT / "config"
CONFIG_EXAMPLE = CONFIG_DIR / "config.example.yaml"
CONFIG_LOCAL = CONFIG_DIR / "config.local.yaml"
WEB_DATA = ROOT / "web_data"
DATASETS_DIR = WEB_DATA / "datasets"
JOBS_DIR = WEB_DATA / "jobs"
REPORT_INDEX = WEB_DATA / "report_index.json"
PRICING_FILE = WEB_DATA / "pricing.json"
SESSION_SECRET_FILE = WEB_DATA / "session_secret.txt"
REQUIRED_DATASET_FILES = [
    "uc1/kb_articles.jsonl",
    "uc1/faq_questions.jsonl",
    "uc2/transcripts.jsonl",
    "uc2/account_lookup.jsonl",
]
SECRET_KEYS = {"api_key", "password", "authorization"}
PUBLIC_PATHS = {"/login", "/api/login", "/static", "/favicon.ico"}

UC_FLOW_STAGES = {
    "uc1": [
        ("load_question", "Load Question", "读取问题"),
        ("embed_query", "Embed Query", "生成问题向量"),
        ("search_knowledge", "Search Knowledge Base", "检索知识库"),
        ("rank_evidence", "Rank Evidence", "证据重排序"),
        ("generate_answer", "Generate Answer", "生成答复"),
        ("record_metrics", "Record Metrics", "记录指标"),
    ],
    "uc2": [
        ("load_transcript", "Load Transcript", "读取通话记录"),
        ("summary", "Summary Agent", "摘要分析"),
        ("sentiment", "Sentiment Agent", "情绪分析"),
        ("compliance", "Compliance Agent", "合规检查"),
        ("qa_score", "QA Score Agent", "质检评分"),
        ("intent_outcome", "Intent Agent", "意图与结果"),
        ("account_tool_call", "Account Tool Call", "账户工具调用"),
        ("account_lookup", "Account Lookup", "查询账户"),
        ("account_context", "Account Context", "账户上下文"),
        ("synthesizer", "Final Insight", "汇总洞察"),
        ("record_metrics", "Record Metrics", "记录指标"),
    ],
    "qdrant": [
        ("validate_dataset", "Validate Dataset", "校验数据集"),
        ("chunk_knowledge", "Split Knowledge", "拆分知识库"),
        ("prepare_collection", "Prepare Index", "准备索引"),
        ("embed_batch", "Create Embeddings", "生成向量"),
        ("upsert_vectors", "Import Index", "导入索引"),
        ("complete", "Complete", "完成"),
    ],
}

STAGE_TYPE_META = {
    "local_python": ("Python", "本地 Python"),
    "embedding_model": ("Embedding", "Embedding 模型"),
    "qdrant": ("Qdrant", "Qdrant 检索"),
    "rerank_model": ("Rerank", "重排序模型"),
    "llm_model": ("LLM", "大模型"),
    "local_record": ("Record", "本地记录"),
}

STAGE_TYPE_BY_ID = {
    "load_question": "local_python",
    "load_transcript": "local_python",
    "validate_dataset": "local_python",
    "chunk_knowledge": "local_python",
    "embed_query": "embedding_model",
    "embed_batch": "embedding_model",
    "search_knowledge": "qdrant",
    "prepare_collection": "qdrant",
    "upsert_vectors": "qdrant",
    "rank_evidence": "rerank_model",
    "summary": "llm_model",
    "sentiment": "llm_model",
    "compliance": "llm_model",
    "qa_score": "llm_model",
    "intent_outcome": "llm_model",
    "account_tool_call": "llm_model",
    "account_context": "llm_model",
    "synthesizer": "llm_model",
    "generate_answer": "llm_model",
    "account_lookup": "local_python",
    "record_metrics": "local_record",
    "report": "local_record",
    "complete": "local_record",
}

UC2_SPECIALIST_STAGE_IDS = {"summary", "sentiment", "compliance", "qa_score", "intent_outcome"}
UC2_ACCOUNT_BRANCH_STAGE_IDS = {"account_tool_call", "account_lookup", "account_context"}

CONFIG_FIELDS = [
    ("Access / 登录", [
        {"path": "web.username", "label": "Login username", "zh": "登录账号", "type": "text", "help": "Used to access this web portal.", "help_zh": "用于登录本测试门户。"},
        {"path": "web.password", "label": "Login password", "zh": "登录密码", "type": "password", "help": "Leave blank to keep the current password.", "help_zh": "留空表示保留当前密码。"},
    ]),
    ("Model APIs / 模型服务", [
        {"path": "llm.base_url", "label": "LLM API base URL", "zh": "大模型 API 地址", "type": "text", "help": "OpenAI-compatible chat completion endpoint base URL.", "help_zh": "兼容 OpenAI chat completions 的基础地址。"},
        {"path": "llm.api_key", "label": "LLM API key", "zh": "大模型 API Key", "type": "password", "help": "Leave blank to keep the current key.", "help_zh": "留空表示保留当前密钥。"},
        {"path": "llm.model", "label": "LLM model name", "zh": "大模型名称", "type": "text", "help": "Model used to generate UC1 answers and UC2 agent outputs.", "help_zh": "用于生成 UC1 答复和 UC2 多 Agent 输出。"},
        {"path": "embedding.base_url", "label": "Embedding API base URL", "zh": "Embedding API 地址", "type": "text", "help": "OpenAI-compatible embeddings endpoint base URL.", "help_zh": "兼容 OpenAI embeddings 的基础地址。"},
        {"path": "embedding.api_key", "label": "Embedding API key", "zh": "Embedding API Key", "type": "password", "help": "Leave blank to keep the current key.", "help_zh": "留空表示保留当前密钥。"},
        {"path": "embedding.model", "label": "Embedding model name", "zh": "Embedding 模型名称", "type": "text", "help": "Model used to build and query the knowledge index.", "help_zh": "用于建立和查询知识库索引。"},
        {"path": "embedding.params", "label": "Embedding extra parameters", "zh": "Embedding 额外参数", "type": "json", "help": "JSON object sent with each embedding request, for example dimensions.", "help_zh": "每次请求一起发送的 JSON 参数，例如 dimensions。"},
    ]),
    ("Reranker / 重排序", [
        {"path": "reranker.enabled", "label": "Enable reranker", "zh": "启用重排序", "type": "bool", "help": "Improves evidence ordering for UC1 when the reranker service is available.", "help_zh": "重排序服务可用时可提升 UC1 证据排序。"},
        {"path": "reranker.base_url", "label": "Reranker API base URL", "zh": "重排序 API 地址", "type": "text", "help": "Base URL for the reranker service.", "help_zh": "重排序服务基础地址。"},
        {"path": "reranker.path", "label": "Reranker path", "zh": "重排序路径", "type": "text", "help": "Request path, for example /rerank or DashScope rerank path.", "help_zh": "请求路径，例如 /rerank 或 DashScope 重排序路径。"},
        {"path": "reranker.request_format", "label": "Reranker request format", "zh": "重排序请求格式", "type": "select", "options": ["openai", "dashscope"], "help": "Choose dashscope for Alibaba Cloud DashScope rerank APIs.", "help_zh": "阿里云 DashScope 重排序接口请选择 dashscope。"},
        {"path": "reranker.api_key", "label": "Reranker API key", "zh": "重排序 API Key", "type": "password", "help": "Leave blank to keep the current key.", "help_zh": "留空表示保留当前密钥。"},
        {"path": "reranker.model", "label": "Reranker model name", "zh": "重排序模型名称", "type": "text", "help": "Model used to rerank retrieved evidence.", "help_zh": "用于对检索证据重新排序。"},
        {"path": "reranker.params", "label": "Reranker extra parameters", "zh": "重排序额外参数", "type": "json", "help": "JSON object sent with each reranker request.", "help_zh": "每次重排序请求一起发送的 JSON 参数。"},
    ]),
    ("Knowledge Index / 知识库索引", [
        {"path": "qdrant.url", "label": "Qdrant URL", "zh": "Qdrant 地址", "type": "text", "help": "Vector database HTTP URL.", "help_zh": "向量数据库 HTTP 地址。"},
        {"path": "qdrant.collection_name", "label": "Collection name", "zh": "集合名称", "type": "text", "help": "Knowledge index collection used by UC1.", "help_zh": "UC1 使用的知识库集合。"},
        {"path": "qdrant.api_key", "label": "Qdrant API key", "zh": "Qdrant API Key", "type": "password", "help": "Leave blank if your Qdrant has no API key.", "help_zh": "没有 API key 可留空。"},
        {"path": "qdrant.username", "label": "Qdrant username", "zh": "Qdrant 用户名", "type": "text", "help": "Optional basic-auth username.", "help_zh": "可选 Basic Auth 用户名。"},
        {"path": "qdrant.password", "label": "Qdrant password", "zh": "Qdrant 密码", "type": "password", "help": "Leave blank to keep the current password.", "help_zh": "留空表示保留当前密码。"},
        {"path": "runtime.qdrant_vector_size", "label": "Vector size", "zh": "向量维度", "type": "number", "help": "Must match the embedding output dimension.", "help_zh": "必须与 Embedding 输出维度一致。"},
    ]),
    ("Runtime Defaults / 运行默认值", [
        {"path": "runtime.timeout_seconds", "label": "API timeout seconds", "zh": "API 超时时间", "type": "number", "help": "Maximum wait time for one API request.", "help_zh": "单次 API 请求最长等待时间。"},
        {"path": "runtime.platform_label", "label": "Platform label", "zh": "平台标签", "type": "text", "help": "Folder label used under runs/.", "help_zh": "runs/ 目录下的结果标签。"},
        {"path": "runtime.top_k", "label": "Retrieved evidence count", "zh": "检索证据数量", "type": "number", "help": "How many KB chunks UC1 retrieves before reranking.", "help_zh": "UC1 重排序前检索多少条知识片段。"},
        {"path": "runtime.rerank_top_n", "label": "Final evidence count", "zh": "最终证据数量", "type": "number", "help": "How many evidence chunks are sent to the LLM.", "help_zh": "最终送给大模型的证据片段数量。"},
        {"path": "runtime.max_tokens", "label": "Max output tokens", "zh": "最大输出 token", "type": "number", "help": "Maximum LLM answer length.", "help_zh": "大模型回答的最大长度。"},
        {"path": "runtime.temperature", "label": "Temperature", "zh": "生成温度", "type": "number", "step": "0.01", "help": "Lower values are more stable for benchmark tests.", "help_zh": "较低数值更适合基准测试。"},
        {"path": "runtime.stream", "label": "Use streaming by default", "zh": "默认启用流式", "type": "bool", "help": "Required for formal TTFT/TPOT metrics.", "help_zh": "正式 TTFT/TPOT 指标需要开启。"},
    ]),
]

for folder in [DATASETS_DIR, JOBS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MaaS Synthetic Benchmark Web Runner")
app.mount("/static", StaticFiles(directory=ROOT / "web_app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "web_app" / "templates")
templates.env.globals["t"] = translate
templates.env.globals["pick"] = pick_text
templates.env.globals["current_lang"] = request_lang
templates.env.globals["language_options"] = language_options


def static_version(path: str) -> str:
    safe_path = path.lstrip("/")
    target = ROOT / "web_app" / "static" / safe_path
    try:
        return str(target.stat().st_mtime_ns)
    except OSError:
        return "1"


templates.env.globals["static_version"] = static_version


def session_secret() -> str:
    if SESSION_SECRET_FILE.exists():
        return SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()
    secret = uuid.uuid4().hex + uuid.uuid4().hex
    SESSION_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_SECRET_FILE.write_text(secret, encoding="utf-8")
    return secret


def sign_session(username: str) -> str:
    issued = str(int(time.time()))
    body = f"{username}:{issued}"
    sig = hmac.new(session_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}:{sig}"


def verify_session(token: str | None) -> str | None:
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    username, issued, sig = parts
    body = f"{username}:{issued}"
    expected = hmac.new(session_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return username


def is_public_path(path: str) -> bool:
    return any(path == public or path.startswith(public + "/") for public in PUBLIC_PATHS)


@app.middleware("http")
async def require_login(request: Request, call_next):
    request.state.lang = request_lang(request)
    requested_lang = request.query_params.get("lang")
    if is_public_path(request.url.path):
        response = await call_next(request)
        if requested_lang in {"en", "zh", "th"}:
            response.set_cookie("benchmark_lang", requested_lang, httponly=False, samesite="lax")
        return response
    username = verify_session(request.cookies.get("benchmark_session"))
    if username:
        request.state.username = username
        response = await call_next(request)
        if requested_lang in {"en", "zh", "th"}:
            response.set_cookie("benchmark_lang", requested_lang, httponly=False, samesite="lax")
        return response
    if request.url.path.startswith("/api/"):
        return Response("Unauthorized", status_code=401)
    response = RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    if requested_lang in {"en", "zh", "th"}:
        response.set_cookie("benchmark_lang", requested_lang, httponly=False, samesite="lax")
    return response


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    for _ in range(3):
        try:
            text = path.read_text(encoding="utf-8")
            if text.strip():
                return json.loads(text)
        except json.JSONDecodeError:
            pass
        time.sleep(0.05)
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_event_log(path: Path | None) -> list[dict[str, Any]]:
    return read_jsonl(path) if path else []


def flow_kind(job: dict[str, Any]) -> str:
    if job.get("kind") == "qdrant_init":
        return "qdrant"
    return str(job.get("uc") or "uc1")


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return ""
    seconds = max(float(seconds), 0.0)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs:02d}s"


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def job_elapsed_seconds(job: dict[str, Any], now_dt: datetime | None = None) -> float | None:
    started = parse_iso_datetime(job.get("started_at") or job.get("created_at"))
    if not started:
        return None
    finished = parse_iso_datetime(job.get("finished_at"))
    end_time = finished or now_dt or datetime.now(timezone.utc).astimezone()
    return max((end_time - started).total_seconds(), 0.0)


def job_elapsed_text(job: dict[str, Any]) -> str:
    return format_seconds(job_elapsed_seconds(job)) or "-"


def stage_type(stage_id: str) -> dict[str, str]:
    type_id = STAGE_TYPE_BY_ID.get(stage_id, "local_python")
    label, zh = STAGE_TYPE_META[type_id]
    return {"id": type_id, "label": label, "zh": zh}


def build_flow_state(job: dict[str, Any], selected_channel_id: str = "", selected_channel_slot: int = 0) -> dict[str, Any]:
    events = read_event_log(Path(job["event_log_path"]) if job.get("event_log_path") else None)
    now_ts = time.time()
    kind = flow_kind(job)
    stage_defs = UC_FLOW_STAGES.get(kind, [])
    stages = [{"id": sid, "label": label, "zh": zh, "status": "pending", "started": 0, "done": 0, "errors": 0, "display_count": "", "type": stage_type(sid)} for sid, label, zh in stage_defs]
    by_id = {stage["id"]: stage for stage in stages}
    started_items: dict[str, set[str]] = {stage["id"]: set() for stage in stages}
    done_items: dict[str, set[str]] = {stage["id"]: set() for stage in stages}
    error_items: dict[str, set[str]] = {stage["id"]: set() for stage in stages}
    stage_durations: dict[str, list[float]] = {stage["id"]: [] for stage in stages}
    stage_order = {sid: idx for idx, (sid, _label, _zh) in enumerate(stage_defs)}
    item_order: list[str] = []
    item_state: dict[str, dict[str, Any]] = {}
    max_concurrency = 0
    total = 0
    completed = 0
    errors = 0
    last_message = ""
    last_message_stage = ""
    import_info = {
        "articles": 0,
        "total_chunks": 0,
        "imported_chunks": 0,
        "collection": "",
        "mode": job.get("mode") or "",
        "percent": 0,
    }
    for event in events:
        stage_id = str(event.get("stage") or "")
        item_id = str(event.get("item_id") or "")
        event_ts = float(event.get("ts") or now_ts)
        concurrency = int(event.get("concurrency") or 0)
        if concurrency > max_concurrency:
            max_concurrency = concurrency
        if event.get("event") == "run_plan":
            total = int(event.get("total_requests") or event.get("total_items") or total or 0)
        if event.get("event") == "progress":
            completed = max(completed, int(event.get("completed") or 0))
            total = max(total, int(event.get("total") or 0))
        if kind == "qdrant":
            if event.get("total_articles") is not None:
                import_info["articles"] = max(int(import_info["articles"]), int(event.get("total_articles") or 0))
            if event.get("total_chunks") is not None:
                import_info["total_chunks"] = max(int(import_info["total_chunks"]), int(event.get("total_chunks") or 0))
                total = max(total, int(event.get("total_chunks") or 0))
            if event.get("collection"):
                import_info["collection"] = str(event.get("collection"))
            if event.get("completed") is not None:
                import_info["imported_chunks"] = max(int(import_info["imported_chunks"]), int(event.get("completed") or 0))
            if event.get("total") is not None:
                import_info["total_chunks"] = max(int(import_info["total_chunks"]), int(event.get("total") or 0))
        if event.get("event") == "request_done":
            completed += 1
            if event.get("status") not in {"ok", None}:
                errors += 1
        if item_id:
            if item_id not in item_state:
                item_order.append(item_id)
                item_state[item_id] = {"item_id": item_id, "sequence": len(item_order), "current_stage": stage_id, "done_stages": set(), "error_stages": set(), "status": "running", "updated": event_ts, "stage_started_at": {}, "stage_finished_at": {}, "stage_outputs": {}}
            state = item_state[item_id]
            state["updated"] = event_ts
            if stage_id:
                state["current_stage"] = stage_id
            if event.get("event") in {"model_output_delta", "stage_done"} and event.get("output_preview"):
                state["stage_outputs"][stage_id] = str(event.get("output_preview"))
            if event.get("event") == "stage_done":
                state["done_stages"].add(stage_id)
                state["stage_finished_at"][stage_id] = event_ts
                started_at = state["stage_started_at"].get(stage_id)
                if started_at is not None:
                    stage_durations.setdefault(stage_id, []).append(max(event_ts - started_at, 0.0))
            elif event.get("event") == "stage_error":
                state["error_stages"].add(stage_id)
                state["stage_finished_at"][stage_id] = event_ts
                state["status"] = "error"
            elif event.get("event") == "request_started":
                state["done_stages"].add(stage_id)
                state["stage_started_at"][stage_id] = event_ts
                state["stage_finished_at"][stage_id] = event_ts
            elif event.get("event") == "request_done":
                state["status"] = "done" if event.get("status") in {"ok", None} else "error"
            elif event.get("event") == "stage_started":
                state["stage_started_at"][stage_id] = event_ts
        if stage_id in by_id:
            stage = by_id[stage_id]
            if event.get("event") in {"stage_started", "job_started"}:
                if item_id:
                    started_items[stage_id].add(item_id)
                else:
                    stage["started"] += 1
            elif event.get("event") in {"stage_done", "progress"}:
                if event.get("event") == "progress":
                    stage["done"] = max(stage["done"], int(event.get("completed") or 0))
                else:
                    if item_id:
                        done_items[stage_id].add(item_id)
                    else:
                        stage["done"] += 1
            elif event.get("event") in {"stage_error"}:
                if item_id:
                    error_items[stage_id].add(item_id)
                else:
                    stage["errors"] += 1
        if event.get("message"):
            message = str(event["message"])
            if stage_id in by_id and " / " in message:
                last_message = message
                last_message_stage = stage_id
            else:
                last_message = message
                last_message_stage = ""
    for stage in stages:
        item_started = len(started_items[stage["id"]])
        item_done = len(done_items[stage["id"]])
        item_errors = len(error_items[stage["id"]])
        active = max(int(stage["started"]) - int(stage["done"]) - int(stage["errors"]), 0) + max(item_started - item_done - item_errors, 0)
        stage["active"] = active
        stage["completed_cases"] = item_done
        stage["error_cases"] = item_errors + int(stage["errors"])
        if stage["errors"] or item_errors:
            stage["status"] = "error"
        elif active:
            stage["status"] = "running"
        elif stage["done"] or item_done:
            stage["status"] = "done"
        else:
            stage["status"] = "pending"
        if total and item_done:
            stage["display_count"] = f"{min(item_done, total)}/{total}"
        elif item_done:
            stage["display_count"] = str(item_done)
        elif kind == "qdrant" and total and stage["done"]:
            stage["display_count"] = f"{min(int(stage['done']), total)}/{total}"
        durations = stage_durations.get(stage["id"], [])
        stage["avg_duration_text"] = format_seconds(sum(durations) / len(durations)) if durations else ""
    if job.get("status") in {"completed", "failed", "stopped"} and stages:
        stages[-1]["status"] = "done" if job["status"] == "completed" else "error"
    if kind == "qdrant":
        if not import_info["total_chunks"]:
            import_info["total_chunks"] = total
        if not import_info["imported_chunks"] and job.get("status") == "completed" and total:
            import_info["imported_chunks"] = total
        if import_info["total_chunks"]:
            import_info["percent"] = min(round(int(import_info["imported_chunks"]) / int(import_info["total_chunks"]) * 100, 1), 100)
    def build_channel_detail(state: dict[str, Any], index: int) -> dict[str, Any]:
        channel_stages = []
        llm_outputs = []
        current_index = stage_order.get(state.get("current_stage", ""), -1)
        for sid, label, zh in stage_defs:
            if sid in {"report", "complete"}:
                continue
            if sid in state["error_stages"]:
                status = "error"
            elif sid in state["done_stages"] or state.get("status") == "done" and stage_order.get(sid, 999) <= current_index:
                status = "done"
            elif sid in state["stage_started_at"] and sid not in state["stage_finished_at"] and state.get("status") == "running":
                status = "running"
            elif sid == state.get("current_stage") and state.get("status") == "running":
                status = "running"
            else:
                status = "pending"
            started_at = state["stage_started_at"].get(sid)
            finished_at = state["stage_finished_at"].get(sid)
            duration_text = ""
            if status == "running" and started_at is not None:
                duration_text = format_seconds(now_ts - started_at)
            elif finished_at is not None and started_at is not None:
                duration_text = format_seconds(finished_at - started_at)
            stage_type_data = stage_type(sid)
            output_preview = str(state.get("stage_outputs", {}).get(sid, ""))
            stage_row = {"id": sid, "label": label, "zh": zh, "status": status, "type": stage_type_data, "duration_text": duration_text, "output_preview": output_preview}
            channel_stages.append(stage_row)
            if stage_type_data["id"] == "llm_model" and (output_preview or status == "running"):
                llm_outputs.append({
                    "id": sid,
                    "label": label,
                    "zh": zh,
                    "status": status,
                    "duration_text": duration_text,
                    "output_preview": output_preview,
                })
        stage_lookup = {stage["id"]: stage for stage in channel_stages}
        uc2_parallel = None
        if kind == "uc2":
            uc2_parallel = {
                "entry": stage_lookup.get("load_transcript"),
                "specialists": [stage_lookup[sid] for sid in ["summary", "sentiment", "compliance", "qa_score", "intent_outcome"] if sid in stage_lookup],
                "account_branch": [stage_lookup[sid] for sid in ["account_tool_call", "account_lookup", "account_context"] if sid in stage_lookup],
                "final": stage_lookup.get("synthesizer"),
                "post": [stage_lookup[sid] for sid in ["record_metrics"] if sid in stage_lookup],
            }
        return {"index": index, "item_id": state["item_id"], "status": state["status"], "stages": channel_stages, "llm_outputs": llm_outputs, "layout": "uc2_parallel" if kind == "uc2" else "linear", "uc2_parallel": uc2_parallel}

    channel_summaries: list[dict[str, Any]] = []
    selected_channel: dict[str, Any] | None = None
    selected_slot = 0
    show_channels = kind in {"uc1", "uc2"} and max_concurrency > 0 and bool(item_state)
    if show_channels:
        def channel_slot(state: dict[str, Any]) -> int:
            sequence = int(state.get("sequence") or 1)
            return ((sequence - 1) % max(max_concurrency, 1)) + 1

        slot_states: dict[int, dict[str, Any]] = {}
        for item_id in item_order:
            state = item_state[item_id]
            slot = channel_slot(state)
            current = slot_states.get(slot)
            if (
                current is None
                or state.get("status") == "running" and current.get("status") != "running"
                or state.get("status") == current.get("status") and float(state.get("updated") or 0) > float(current.get("updated") or 0)
            ):
                slot_states[slot] = state
        chosen = [(slot, slot_states[slot]) for slot in sorted(slot_states)]
        if selected_channel_slot in slot_states:
            selected_slot = selected_channel_slot
        elif selected_channel_id and selected_channel_id in item_state:
            selected_slot = channel_slot(item_state[selected_channel_id])
        selected_state = slot_states.get(selected_slot) if selected_slot else None
        if not selected_state:
            selected_pair = next(((slot, state) for slot, state in chosen if state.get("status") == "running"), None)
            if selected_pair:
                selected_slot, selected_state = selected_pair
        if not selected_state and chosen:
            selected_slot, selected_state = max(chosen, key=lambda row: float(row[1].get("updated") or 0))
        for slot, state in chosen:
            current_stage = str(state.get("current_stage") or "")
            summary = {"index": slot, "item_id": state["item_id"], "status": state["status"], "current_stage": current_stage}
            channel_summaries.append(summary)
            if selected_state and state["item_id"] == selected_state["item_id"]:
                selected_channel = build_channel_detail(state, slot)
    progress_total = max(int(total or 0), 0)
    progress_completed = max(int(completed or 0), 0)
    progress_errors = max(int(errors or 0), 0)
    bar_total = progress_total if progress_total > 0 else max(progress_completed, progress_errors, 1)
    bar_errors = min(progress_errors, bar_total)
    bar_completed = min(progress_completed, bar_total)
    bar_success = max(bar_completed - bar_errors, 0)
    bar_pending = max(bar_total - bar_success - bar_errors, 0)

    def progress_percent(value: int) -> float:
        return round(value / bar_total * 100, 2) if bar_total > 0 else 0.0

    return {
        "kind": kind,
        "stages": stages,
        "channels": [selected_channel] if selected_channel else [],
        "channel_summaries": channel_summaries,
        "selected_channel": selected_channel,
        "selected_slot": selected_slot,
        "show_channels": show_channels,
        "max_concurrency": max_concurrency,
        "events": events[-20:],
        "completed": completed,
        "total": total,
        "errors": errors,
        "elapsed_text": job_elapsed_text(job),
        "progress": {
            "completed": progress_completed,
            "total": progress_total,
            "success": bar_success,
            "pending": bar_pending,
            "errors": progress_errors,
            "success_percent": progress_percent(bar_success),
            "pending_percent": progress_percent(bar_pending),
            "error_percent": progress_percent(bar_errors),
        },
        "last_message": last_message,
        "last_message_stage": last_message_stage,
        "import": import_info,
    }


def load_config_yaml(path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from config_utils import load_config

    return load_config(path)


def effective_config_path() -> Path:
    return CONFIG_LOCAL if CONFIG_LOCAL.exists() else CONFIG_EXAMPLE


def deep_merge(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_effective_config() -> dict[str, Any]:
    if CONFIG_LOCAL.exists():
        return deep_merge(load_config_yaml(CONFIG_EXAMPLE), load_config_yaml(CONFIG_LOCAL))
    return load_config_yaml(CONFIG_EXAMPLE)


def get_path(config: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_path(config: dict[str, Any], dotted: str, value: Any) -> None:
    node: dict[str, Any] = config
    parts = dotted.split(".")
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(yaml_scalar(v) for v in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def dump_simple_yaml(data: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    for key, value in data.items():
        prefix = " " * indent + f"{key}:"
        if isinstance(value, dict):
            lines.append(prefix)
            if value:
                lines.append(dump_simple_yaml(value, indent + 2))
        else:
            lines.append(prefix + " " + yaml_scalar(value))
    return "\n".join(lines)


def save_config_yaml(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_simple_yaml(config).rstrip() + "\n", encoding="utf-8")


def field_value(config: dict[str, Any], field: dict[str, Any]) -> str:
    value = get_path(config, field["path"], "")
    if field["type"] == "json":
        return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False, indent=2)
    if field["type"] == "bool":
        return "true" if bool(value) else "false"
    if field["type"] == "password":
        return ""
    return "" if value is None else str(value)


def config_form_sections(config: dict[str, Any]) -> list[dict[str, Any]]:
    sections = []
    for title, fields in CONFIG_FIELDS:
        prepared = []
        for field in fields:
            prepared.append({**field, "value": field_value(config, field), "current_set": bool(get_path(config, field["path"], ""))})
        sections.append({"title": title, "fields": prepared})
    return sections


def parse_form_value(field: dict[str, Any], raw: str, old_value: Any, local_exists: bool) -> Any:
    if field["type"] == "password" and raw == "" and local_exists:
        return old_value
    if field["type"] == "bool":
        return raw == "true"
    if field["type"] == "number":
        if "." in raw or field.get("step"):
            return float(raw)
        return int(raw)
    if field["type"] == "json":
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"{field['label']} must be a JSON object")
        return parsed
    return raw


def save_config_from_form(form: dict[str, Any]) -> None:
    local_exists = CONFIG_LOCAL.exists()
    config = load_effective_config()
    for _title, fields in CONFIG_FIELDS:
        for field in fields:
            raw = str(form.get(field["path"], ""))
            value = parse_form_value(field, raw, get_path(config, field["path"], ""), local_exists)
            set_path(config, field["path"], value)
    if not get_path(config, "runtime.output_dir"):
        set_path(config, "runtime.output_dir", "runs")
    if not get_path(config, "runtime.concurrency_levels"):
        set_path(config, "runtime.concurrency_levels", [1, 4, 16, 64])
    if not get_path(config, "runtime.runs_per_platform"):
        set_path(config, "runtime.runs_per_platform", 1)
    if not get_path(config, "runtime.concurrency"):
        set_path(config, "runtime.concurrency", 1)
    metrics = get_path(config, "metrics")
    if not isinstance(metrics, dict):
        set_path(config, "metrics", {
            "record_per_call_logs": True,
            "aggregate_percentiles": [50, 95],
            "record_usage_tokens": True,
            "record_ttft_tpot": True,
            "record_error_rate": True,
        })
    save_config_yaml(CONFIG_LOCAL, config)


def save_pricing_values(pricing: dict[str, Any]) -> None:
    normalized = {
        "input_per_1m": float(pricing.get("input_per_1m") or 0),
        "output_per_1m": float(pricing.get("output_per_1m") or 0),
        "currency": pricing.get("currency") or "USD",
    }
    write_json(PRICING_FILE, normalized)
    config = load_effective_config()
    set_path(config, "pricing", normalized)
    save_config_yaml(CONFIG_LOCAL, config)


def validate_local_config() -> list[str]:
    if not CONFIG_LOCAL.exists():
        return ["config.local.yaml has not been saved yet / 尚未保存本地配置"]
    sys.path.insert(0, str(SCRIPTS_DIR))
    from config_utils import validate_config

    return validate_config(load_config_yaml(CONFIG_LOCAL), allow_placeholders=False)


def local_config_ready() -> bool:
    return not validate_local_config()


def mask_config(value: Any, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {key: mask_config(child, key) for key, child in value.items()}
    if parent_key in SECRET_KEYS and value:
        text = str(value)
        if text.startswith("REPLACE_WITH_"):
            return text
        return "***MASKED***"
    return value


def config_files() -> list[Path]:
    return sorted([p for p in CONFIG_DIR.glob("*.y*ml") if p.is_file()])


def dataset_meta_path(dataset_id: str) -> Path:
    return DATASETS_DIR / dataset_id / "metadata.json"


def dataset_data_dir(dataset_id: str) -> Path:
    return DATASETS_DIR / dataset_id / "benchmark_data"


def validate_dataset_dir(data_dir: Path) -> tuple[bool, list[str], dict[str, int]]:
    missing = [rel for rel in REQUIRED_DATASET_FILES if not (data_dir / rel).exists()]
    counts: dict[str, int] = {}
    for rel in REQUIRED_DATASET_FILES:
        path = data_dir / rel
        counts[rel] = len(read_jsonl(path)) if path.exists() else 0
    return not missing, missing, counts


def list_datasets() -> list[dict[str, Any]]:
    rows = []
    for meta_file in sorted(DATASETS_DIR.glob("*/metadata.json"), reverse=True):
        try:
            rows.append(read_json(meta_file, {}))
        except Exception:
            continue
    return rows


def ensure_default_dataset() -> None:
    default_id = "default_benchmark_data"
    target = DATASETS_DIR / default_id
    if dataset_meta_path(default_id).exists():
        return
    source = ROOT / "benchmark_data"
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    valid, missing, counts = validate_dataset_dir(source)
    write_json(dataset_meta_path(default_id), {
        "dataset_id": default_id,
        "name": "Built-in benchmark_data",
        "created_at": now_iso(),
        "source": "local benchmark_data",
        "data_dir": str(source),
        "valid": valid,
        "missing": missing,
        "counts": counts,
        "qdrant": {},
    })


def load_pricing() -> dict[str, float]:
    data = read_json(PRICING_FILE, {"input_per_1m": 0.0, "output_per_1m": 0.0, "currency": "USD"})
    if CONFIG_LOCAL.exists():
        try:
            config_pricing = get_path(load_config_yaml(CONFIG_LOCAL), "pricing", {})
            if isinstance(config_pricing, dict):
                data.update({key: value for key, value in config_pricing.items() if value is not None})
        except Exception:
            pass
    return {
        "input_per_1m": float(data.get("input_per_1m") or 0),
        "output_per_1m": float(data.get("output_per_1m") or 0),
        "currency": data.get("currency") or "USD",
    }


def load_report_index() -> list[dict[str, Any]]:
    return read_json(REPORT_INDEX, [])


def save_report_index(rows: list[dict[str, Any]]) -> None:
    write_json(REPORT_INDEX, rows)


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def load_job(job_id: str) -> dict[str, Any]:
    data = read_json(job_path(job_id), {})
    if not data:
        raise HTTPException(status_code=404, detail="job not found")
    return data


def list_jobs(limit: int | None = None, status: str = "", kind: str = "", uc: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in JOBS_DIR.glob("*.json"):
        try:
            job = read_json(path, {})
        except Exception:
            continue
        if not job.get("job_id"):
            continue
        if status and job.get("status") != status:
            continue
        if kind and job.get("kind") != kind:
            continue
        if uc and job.get("uc") != uc:
            continue
        job["elapsed_text"] = job_elapsed_text(job)
        rows.append(job)
    rows.sort(key=lambda row: row.get("started_at") or row.get("created_at") or "", reverse=True)
    return rows[:limit] if limit else rows


def save_job(job: dict[str, Any]) -> None:
    write_json(job_path(job["job_id"]), job)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def unlink_local_file(path_value: Any) -> None:
    if not path_value:
        return
    path = Path(str(path_value)).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    if path.exists() and path.is_file() and is_relative_to(path, ROOT):
        path.unlink(missing_ok=True)


def remove_report_entries(job_ids: list[str], delete_files: bool = True) -> None:
    if not job_ids:
        return
    id_set = set(job_ids)
    reports = load_report_index()
    kept = []
    for report in reports:
        if report.get("job_id") in id_set:
            if delete_files:
                unlink_local_file(report.get("raw_log_path"))
                unlink_local_file(report.get("summary_path"))
            continue
        kept.append(report)
    save_report_index(kept)


def clear_report_fields_from_jobs(job_ids: list[str]) -> None:
    for job_id in job_ids:
        path = job_path(job_id)
        if not path.exists():
            continue
        job = read_json(path, {})
        changed = False
        for key in ["raw_log_path", "summary_path"]:
            if key in job:
                job.pop(key, None)
                changed = True
        if changed:
            save_job(job)


def delete_reports(job_ids: list[str]) -> None:
    remove_report_entries(job_ids, delete_files=True)
    clear_report_fields_from_jobs(job_ids)


def stop_job_process(job: dict[str, Any]) -> None:
    if job.get("status") in {"completed", "failed", "stopped"}:
        return
    pid = int(job.get("process_group_id") or job.get("pid") or 0)
    if pid:
        request_stop_process(pid)


def delete_jobs(job_ids: list[str]) -> None:
    for job_id in job_ids:
        path = job_path(job_id)
        if not path.exists():
            continue
        job = read_json(path, {})
        stop_job_process(job)
        unlink_local_file(job.get("log_path"))
        unlink_local_file(job.get("event_log_path"))
        path.unlink(missing_ok=True)


def delete_datasets(dataset_ids: list[str]) -> None:
    for dataset_id in dataset_ids:
        target = DATASETS_DIR / dataset_id
        if target.exists() and target.is_dir() and is_relative_to(target, DATASETS_DIR):
            shutil.rmtree(target)


def request_stop_process(pid: int, timeout_seconds: float = 3.0) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return


def tail_text(path: Path | None, lines: int = 80) -> str:
    if not path or not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cleaned: list[str] = []
    seen_progress: set[tuple[str, str, str, str]] = set()
    progress_pattern = re.compile(r"run\s+(\d+/\d+)\s+concurrency=(\d+).+?(\d+(?:\.\d+)?)%\s+(\d+/\d+).+?err=(\d+)")
    for raw_line in content:
        line = raw_line.strip()
        if not line:
            continue
        if "benchmark:run" in line:
            match = progress_pattern.search(line)
            if match:
                key = (match.group(1), match.group(2), match.group(4), match.group(5))
                if key in seen_progress:
                    continue
                seen_progress.add(key)
                line = re.sub(r"^[\\|/\\-]\s*", "", line)
            else:
                continue
        cleaned.append(line)
    return "\n".join(cleaned[-lines:])


def existing_raw_logs() -> set[Path]:
    return {path.resolve() for path in ROOT.glob("runs/**/uc*_raw_logs_*.jsonl") if path.is_file()}


def infer_summary_path(raw_path: Path) -> Path:
    return raw_path.with_name(raw_path.name.replace("_raw_logs_", "_summary_").replace(".jsonl", ".json"))


def percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    pos = (len(ordered) - 1) * pct / 100
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    weight = pos - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def distribution(values: list[float]) -> dict[str, float | None]:
    return {
        "mean": round(statistics.mean(values), 4) if values else None,
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
    }


def row_token_value(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    if value is not None:
        return int(value or 0)
    return sum(int(call.get(key) or 0) for call in row.get("calls") or [])


def row_cost(row: dict[str, Any], pricing: dict[str, Any]) -> float:
    input_cost = row_token_value(row, "input_tokens") / 1_000_000 * float(pricing.get("input_per_1m") or 0)
    output_cost = row_token_value(row, "output_tokens") / 1_000_000 * float(pricing.get("output_per_1m") or 0)
    return input_cost + output_cost


def agent_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for call in row.get("calls") or []:
            agent = str(call.get("agent") or "unknown")
            buckets.setdefault(agent, []).append(call)
    breakdown = []
    for agent, calls in sorted(buckets.items()):
        ok_calls = [call for call in calls if call.get("status") in {"ok", None} or call.get("mode") == "dry-run"]
        breakdown.append({
            "agent": agent,
            "calls": len(calls),
            "completed": len(ok_calls),
            "errors": len(calls) - len(ok_calls),
            "latency": distribution([float(call["latency_ms"]) for call in ok_calls if call.get("latency_ms") is not None]),
            "ttft": distribution([float(call["ttft_ms"]) for call in ok_calls if call.get("ttft_ms") is not None]),
            "tpot": distribution([float(call["tpot_ms"]) for call in ok_calls if call.get("tpot_ms") is not None]),
            "input_tokens": {"sum": sum(int(call.get("input_tokens") or 0) for call in ok_calls), **distribution([float(call.get("input_tokens") or 0) for call in ok_calls])},
            "output_tokens": {"sum": sum(int(call.get("output_tokens") or 0) for call in ok_calls), **distribution([float(call.get("output_tokens") or 0) for call in ok_calls])},
            "total_tokens": {"sum": sum(int(call.get("total_tokens") or 0) for call in ok_calls), **distribution([float(call.get("total_tokens") or 0) for call in ok_calls])},
        })
    return breakdown


def agent_chart_maxima(breakdown: list[dict[str, Any]]) -> dict[str, float]:
    def max_path(*keys: str) -> float:
        values: list[float] = []
        for row in breakdown:
            value: Any = row
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            if value is not None:
                values.append(float(value or 0))
        maximum = max(values or [0])
        return maximum if maximum > 0 else 1.0

    return {
        "calls": max_path("calls"),
        "errors": max_path("errors"),
        "latency_p95": max_path("latency", "p95"),
        "ttft_p95": max_path("ttft", "p95"),
        "tpot_p95": max_path("tpot", "p95"),
        "input_tokens": max_path("input_tokens", "sum"),
        "output_tokens": max_path("output_tokens", "sum"),
        "total_tokens": max_path("total_tokens", "sum"),
    }


def new_job_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def count_uc1_chunks(data_dir: Path) -> int:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from build_qdrant_index import chunk_text

    articles = read_jsonl(data_dir / "uc1" / "kb_articles.jsonl")
    return sum(len(chunk_text(article.get("body", ""))) for article in articles)


def normalize_uploaded_zip(upload_path: Path, dataset_id: str, name: str) -> dict[str, Any]:
    target = DATASETS_DIR / dataset_id
    extract_dir = target / "uploaded"
    if target.exists():
        shutil.rmtree(target)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(upload_path) as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"unsafe zip entry: {member.filename}")
        zf.extractall(extract_dir)

    candidates = [extract_dir / "benchmark_data"] + list(extract_dir.glob("*/benchmark_data"))
    source_data = next((p for p in candidates if p.exists()), None)
    if not source_data:
        raise ValueError("ZIP must contain benchmark_data/ or */benchmark_data/")
    final_data = target / "benchmark_data"
    shutil.copytree(source_data, final_data)
    valid, missing, counts = validate_dataset_dir(final_data)
    meta = {
        "dataset_id": dataset_id,
        "name": name or dataset_id,
        "created_at": now_iso(),
        "source": upload_path.name,
        "data_dir": str(final_data),
        "valid": valid,
        "missing": missing,
        "counts": counts,
        "qdrant": {},
    }
    write_json(dataset_meta_path(dataset_id), meta)
    return meta


def run_subprocess_job(job: dict[str, Any], cmd: list[str]) -> None:
    current = read_json(job_path(job["job_id"]), job)
    if current.get("stop_requested") or current.get("status") == "stopped":
        current["status"] = "stopped"
        current["finished_at"] = now_iso()
        current["return_code"] = None
        save_job(current)
        return
    job["status"] = "running"
    job["started_at"] = now_iso()
    job["command"] = cmd
    job["log_path"] = str(JOBS_DIR / f"{job['job_id']}.log")
    save_job(job)
    before = existing_raw_logs()
    log_path = Path(job["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
        job["pid"] = process.pid
        job["process_group_id"] = process.pid
        save_job(job)
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
        return_code = process.wait()
    after = existing_raw_logs()
    raw_logs = sorted(after - before, key=lambda p: p.stat().st_mtime)
    latest_job = read_json(job_path(job["job_id"]), job)
    was_stopped = bool(latest_job.get("stop_requested")) or latest_job.get("status") == "stopping" or return_code in {-15, -9}
    job.update({key: value for key, value in latest_job.items() if key in {"stop_requested", "stop_requested_at", "stop_message"}})
    job["finished_at"] = now_iso()
    job["return_code"] = return_code
    job["status"] = "stopped" if was_stopped else ("completed" if return_code == 0 else "failed")
    job.pop("pid", None)
    job.pop("process_group_id", None)
    if raw_logs:
        raw_path = raw_logs[-1]
        job["raw_log_path"] = str(raw_path)
        summary_path = infer_summary_path(raw_path)
        if summary_path.exists():
            job["summary_path"] = str(summary_path)
    save_job(job)
    if job.get("kind") == "uc_run":
        if job["status"] == "completed":
            upsert_report(job)
    elif job.get("kind") == "qdrant_init":
        update_dataset_qdrant_meta(job)


def update_dataset_qdrant_meta(job: dict[str, Any]) -> None:
    dataset_id = job.get("dataset_id")
    if not dataset_id:
        return
    meta_path = dataset_meta_path(dataset_id)
    meta = read_json(meta_path, None)
    if not meta:
        return
    collection = ""
    chunk_count = 0
    try:
        config = load_config_yaml(CONFIG_DIR / job["config"])
        collection = get_path(config, "qdrant.collection_name", "")
        chunk_count = count_uc1_chunks(Path(meta["data_dir"]))
    except Exception:
        pass
    meta["qdrant"] = {
        "last_job_id": job["job_id"],
        "status": job.get("status"),
        "mode": job.get("mode"),
        "config": job.get("config"),
        "collection": collection,
        "chunk_count": chunk_count,
        "finished_at": job.get("finished_at"),
    }
    write_json(meta_path, meta)


def upsert_report(job: dict[str, Any]) -> None:
    reports = load_report_index()
    reports = [row for row in reports if row.get("job_id") != job["job_id"]]
    pricing = job.get("pricing") or load_pricing()
    platform_label = infer_platform_label(job)
    reports.append({
        "job_id": job["job_id"],
        "uc": job.get("uc"),
        "dataset_id": job.get("dataset_id"),
        "config": job.get("config"),
        "params": job.get("params"),
        "platform_label": platform_label,
        "status": job.get("status"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "raw_log_path": job.get("raw_log_path"),
        "summary_path": job.get("summary_path"),
        "pricing": pricing,
    })
    reports.sort(key=lambda row: row.get("started_at") or "", reverse=True)
    save_report_index(reports)


def infer_platform_label(report: dict[str, Any]) -> str:
    params = report.get("params") if isinstance(report.get("params"), dict) else {}
    for value in [
        params.get("platform_label") if params else None,
        report.get("platform_label"),
        report.get("platform"),
    ]:
        if value:
            return str(value)

    raw_path = str(report.get("raw_log_path") or report.get("summary_path") or "")
    if raw_path:
        parts = Path(raw_path).parts
        if "runs" in parts:
            index = parts.index("runs")
            if index + 1 < len(parts):
                return parts[index + 1]

    config_name = str(report.get("config") or CONFIG_LOCAL.name)
    config_path = CONFIG_DIR / config_name
    if config_path.exists():
        try:
            config = load_config_yaml(config_path)
            value = get_path(config, "runtime.platform_label", "")
            if value:
                return str(value)
        except Exception:
            pass
    return "platform"


def pdf_watermark_label(report: dict[str, Any]) -> str:
    value = infer_platform_label(report)
    cleaned = re.sub(r"[^0-9A-Za-z._ -]+", "", value).strip()
    return (cleaned or "platform").upper()


def parse_report_datetime(value: Any) -> datetime | None:
    return parse_iso_datetime(value)


def resolve_timezone(tz_name: str | None) -> ZoneInfo | None:
    if not tz_name:
        return None
    try:
        return ZoneInfo(str(tz_name))
    except Exception:
        return None


def format_report_datetime(value: Any, tz_name: str | None = None) -> str:
    target_tz = resolve_timezone(tz_name)
    if not target_tz:
        return str(value or "-")
    parsed = parse_report_datetime(value)
    if not parsed:
        return str(value or "-")
    parsed = parsed.astimezone(target_tz)
    return parsed.strftime("%Y-%m-%d %H:%M:%S %Z")


def report_date_label(report: dict[str, Any], tz_name: str | None = None) -> str:
    target_tz = resolve_timezone(tz_name)
    for key in ("started_at", "finished_at", "created_at"):
        value = str(report.get(key) or "")
        if target_tz:
            parsed = parse_report_datetime(value)
            if parsed:
                parsed = parsed.astimezone(target_tz)
                return parsed.strftime("%Y-%m-%d_%H-%M-%S")
        match = re.search(r"(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}):(\d{2}))?", value)
        if match:
            if match.group(2):
                return f"{match.group(1)}_{match.group(2)}-{match.group(3)}-{match.group(4)}"
            return f"{match.group(1)}_00-00-00"
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def safe_filename_component(value: Any, fallback: str = "value", ascii_only: bool = False) -> str:
    text = str(value or "").strip()
    if ascii_only:
        text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    else:
        text = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", text)
        text = re.sub(r"\s+", "_", text)
    text = text.strip("._-")
    return text or fallback


def report_pdf_filename(report: dict[str, Any], data: dict[str, Any], ascii_only: bool = False, tz_name: str | None = None) -> str:
    metrics = data.get("required_metrics") if isinstance(data.get("required_metrics"), dict) else {}
    uc = safe_filename_component(metrics.get("uc") or report.get("uc") or "uc", "uc", ascii_only)
    platform = safe_filename_component(infer_platform_label(report), "platform", ascii_only)
    date_label = safe_filename_component(report_date_label(report, tz_name), "date", ascii_only)
    return f"{uc}_{platform}_{date_label}.pdf"


def summarize_report(raw_path: Path | None, summary_path: Path | None, pricing: dict[str, Any]) -> dict[str, Any]:
    rows = read_jsonl(raw_path) if raw_path else []
    summary = read_json(summary_path, {}) if summary_path else {}
    for row in rows:
        row["_input_tokens"] = row_token_value(row, "input_tokens")
        row["_output_tokens"] = row_token_value(row, "output_tokens")
        row["_total_tokens"] = row_token_value(row, "total_tokens")
        row["_cost"] = row_cost(row, pricing)
    ok_rows = [row for row in rows if row.get("status") == "ok" or row.get("mode") == "dry-run"]
    total_input = sum(row_token_value(row, "input_tokens") for row in ok_rows)
    total_output = sum(row_token_value(row, "output_tokens") for row in ok_rows)
    total_tokens = sum(row_token_value(row, "total_tokens") for row in ok_rows)
    input_cost = total_input / 1_000_000 * float(pricing.get("input_per_1m") or 0)
    output_cost = total_output / 1_000_000 * float(pricing.get("output_per_1m") or 0)
    row_costs = [row_cost(row, pricing) for row in ok_rows]
    request_count = len(rows)
    ok_count = len(ok_rows)
    uc = str(rows[0].get("uc") if rows else summary.get("uc") or "")
    is_uc2 = uc == "uc2"
    throughput_label = "Transcripts/hour" if is_uc2 else "Requests/min"
    cost_unit_label = "per transcript" if is_uc2 else "per request"
    agents = agent_breakdown(ok_rows)
    return {
        "rows": rows,
        "summary": summary,
        "status_counts": {status: sum(1 for r in rows if r.get("status") == status) for status in sorted({r.get("status") for r in rows})},
        "tokens": {"input": total_input, "output": total_output, "total": total_tokens},
        "cost": {"input": input_cost, "output": output_cost, "total": input_cost + output_cost, "currency": pricing.get("currency", "USD")},
        "pricing": {
            "input_per_1m": float(pricing.get("input_per_1m") or 0),
            "output_per_1m": float(pricing.get("output_per_1m") or 0),
            "currency": pricing.get("currency", "USD"),
            "unit": "per 1M tokens",
        },
        "required_metrics": {
            "uc": uc,
            "requests": request_count,
            "completed": ok_count,
            "errors": request_count - ok_count,
            "error_rate": round((request_count - ok_count) / max(request_count, 1), 4),
            "latency": distribution([float(row["latency_ms"]) for row in ok_rows if row.get("latency_ms") is not None]),
            "ttft": distribution([float(row["ttft_ms"]) for row in ok_rows if row.get("ttft_ms") is not None]),
            "tpot": distribution([float(row["tpot_ms"]) for row in ok_rows if row.get("tpot_ms") is not None]),
            "uc1_llm_latency": distribution([float(row["llm_latency_ms"]) for row in ok_rows if row.get("llm_latency_ms") is not None]),
            "uc1_llm_ttft": distribution([float(row["llm_ttft_ms"]) for row in ok_rows if row.get("llm_ttft_ms") is not None]),
            "uc1_llm_tpot": distribution([float(row["llm_tpot_ms"]) for row in ok_rows if row.get("llm_tpot_ms") is not None]),
            "has_uc1_llm_metrics": any(row.get("llm_latency_ms") is not None for row in ok_rows),
            "input_tokens": {"sum": total_input, **distribution([float(row_token_value(row, "input_tokens")) for row in ok_rows])},
            "output_tokens": {"sum": total_output, **distribution([float(row_token_value(row, "output_tokens")) for row in ok_rows])},
            "total_tokens": {"sum": total_tokens, **distribution([float(row_token_value(row, "total_tokens")) for row in ok_rows])},
            "cost_per_item": distribution(row_costs),
            "cost_per_1k_items": round((sum(row_costs) / max(ok_count, 1)) * 1000, 6) if ok_rows else None,
            "cost_per_run": input_cost + output_cost,
            "cost_unit_label": cost_unit_label,
            "throughput_label": throughput_label,
            "transcripts_per_hour": [round(float(item.get("rpm") or 0) * 60, 4) for item in summary.get("summaries", [])] if is_uc2 else [],
            "summary_rows": summary.get("summaries", []),
            "agent_breakdown": agents,
            "agent_chart_max": agent_chart_maxima(agents),
            "sla_status": "N/A - SLA thresholds not configured",
            "network_rtt": "N/A - ping/traceroute not captured by harness",
            "test_window": "Use report start/end timestamps; formal banking traffic window must be recorded by operator.",
            "batch_discount": "Not applied unless token price inputs already include the platform discount.",
        },
    }


def report_lookup(job_id: str) -> dict[str, Any]:
    reports = load_report_index()
    report = next((row for row in reports if row.get("job_id") == job_id), None)
    if not report:
        report = load_job(job_id)
        report = {**report, "pricing": report.get("pricing") or load_pricing()}
    return report


def pdf_text(value: Any, limit: int = 1200) -> str:
    text = str(value if value is not None else "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def fmt_seconds(ms: Any) -> str:
    if ms is None:
        return "N/A"
    try:
        return f"{float(ms) / 1000:.2f}s"
    except Exception:
        return "N/A"


def fmt_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}{suffix}"
    return f"{value}{suffix}"


def fmt_token_triplet(values: dict[str, Any]) -> str:
    return f"{values.get('sum', 0)} / {fmt_value(values.get('p50'))} / {fmt_value(values.get('p95'))}"


def generate_report_pdf(job_id: str, report: dict[str, Any], data: dict[str, Any], tz_name: str | None = None) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF dependency missing: {exc}. Run ./start_web.sh to install web dependencies.")

    font_name = "Helvetica"
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]:
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("BenchmarkUnicode", candidate))
                font_name = "BenchmarkUnicode"
                break
            except Exception:
                continue

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("BenchmarkTitle", parent=styles["Title"], fontName=font_name, fontSize=18, leading=22, alignment=TA_LEFT)
    h2_style = ParagraphStyle("BenchmarkH2", parent=styles["Heading2"], fontName=font_name, fontSize=12, leading=15, spaceBefore=8, spaceAfter=5)
    body_style = ParagraphStyle("BenchmarkBody", parent=styles["BodyText"], fontName=font_name, fontSize=8.5, leading=11)
    small_style = ParagraphStyle("BenchmarkSmall", parent=body_style, fontSize=7.2, leading=9)
    page_width, _page_height = landscape(A4)
    table_width = page_width - 20 * mm

    def p(value: Any, style: ParagraphStyle = body_style) -> Paragraph:
        import html
        return Paragraph(html.escape(pdf_text(value)), style)

    def table(rows: list[list[Any]], widths: list[float] | None = None) -> Table:
        rendered = [[cell if hasattr(cell, "wrap") else p(cell, small_style) for cell in row] for row in rows]
        column_count = max((len(row) for row in rows), default=1)
        if widths and len(widths) == column_count and sum(widths) > 0:
            scale = table_width / sum(widths)
            col_widths = [width * scale for width in widths]
        else:
            col_widths = [table_width / column_count for _ in range(column_count)]
        tbl = Table(rendered, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4fa")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dce3ea")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl

    m = data["required_metrics"]
    currency = data["cost"]["currency"]
    platform_label = pdf_watermark_label(report)
    started_label = format_report_datetime(report.get("started_at"), tz_name)
    finished_label = format_report_datetime(report.get("finished_at"), tz_name)
    logo_path = ROOT / "web_app" / "static" / "assets" / "client-logo.jpg"
    story: list[Any] = [
    ]
    if logo_path.exists():
        logo = Image(str(logo_path), width=44 * mm, height=19.7 * mm)
        title = Table([[logo, p("MaaS Benchmark Report", title_style)]], colWidths=[50 * mm, table_width - 50 * mm], hAlign="LEFT")
        title.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(title)
    else:
        story.append(p("MaaS Benchmark Report", title_style))
    story += [
        p(f"Platform: {platform_label}", h2_style),
        p(f"Job: {job_id}"),
        p(f"UC: {m.get('uc') or report.get('uc') or '-'} | Dataset: {report.get('dataset_id', '-')} | Status: {report.get('status', '-')}"),
        p(f"Started: {started_label} | Finished: {finished_label}"),
        Spacer(1, 5 * mm),
        p("Executive Summary", h2_style),
        table([
            ["Requests", "Completed", "Errors", "Error rate", "Latency P95", "Total tokens", "Total cost"],
            [m["requests"], m["completed"], m["errors"], m["error_rate"], fmt_seconds(m["latency"]["p95"]), m["total_tokens"]["sum"], f"{currency} {m['cost_per_run']:.6f}"],
        ]),
        p("Pricing Used", h2_style),
        table([
            ["Unit", "Input price", "Output price", "Cost formula"],
            ["Per 1M tokens", f"{currency} {data['pricing']['input_per_1m']:.6f}", f"{currency} {data['pricing']['output_per_1m']:.6f}", "tokens / 1,000,000 * price"],
        ], [38 * mm, 38 * mm, 38 * mm, 111 * mm]),
        p("Core Metrics", h2_style),
        table([
            ["Metric", "Mean", "P50", "P95", "Notes"],
            ["End-to-end latency", fmt_seconds(m["latency"]["mean"]), fmt_seconds(m["latency"]["p50"]), fmt_seconds(m["latency"]["p95"]), "Successful requests only"],
            ["TTFT", fmt_seconds(m["ttft"]["mean"]), fmt_seconds(m["ttft"]["p50"]), fmt_seconds(m["ttft"]["p95"]), "Streaming metric; no-stream is not formal"],
            ["TPOT", fmt_value(m["tpot"]["mean"], " ms/token"), fmt_value(m["tpot"]["p50"], " ms/token"), fmt_value(m["tpot"]["p95"], " ms/token"), "Network-robust latency metric"],
            ["Input tokens", fmt_value(m["input_tokens"]["mean"]), fmt_value(m["input_tokens"]["p50"]), fmt_value(m["input_tokens"]["p95"]), f"Sum {m['input_tokens']['sum']}"],
            ["Output tokens", fmt_value(m["output_tokens"]["mean"]), fmt_value(m["output_tokens"]["p50"]), fmt_value(m["output_tokens"]["p95"]), f"Sum {m['output_tokens']['sum']}"],
            ["Total tokens", fmt_value(m["total_tokens"]["mean"]), fmt_value(m["total_tokens"]["p50"]), fmt_value(m["total_tokens"]["p95"]), f"Sum {m['total_tokens']['sum']}"],
            [f"Cost {m['cost_unit_label']}", f"{currency} {m['cost_per_item']['mean'] or 0:.6f}", f"{currency} {m['cost_per_item']['p50'] or 0:.6f}", f"{currency} {m['cost_per_item']['p95'] or 0:.6f}", "Based on configured token prices"],
            ["Input cost", "", "", f"{currency} {data['cost']['input'] or 0:.6f}", "Recalculated with current input token price"],
            ["Output cost", "", "", f"{currency} {data['cost']['output'] or 0:.6f}", "Recalculated with current output token price"],
            ["Cost per 1K items", "", "", f"{currency} {m['cost_per_1k_items'] or 0:.6f}", "Items = request or transcript"],
            ["Cost per run", "", "", f"{currency} {m['cost_per_run'] or 0:.6f}", m["batch_discount"]],
        ], [42*mm, 28*mm, 28*mm, 28*mm, 98*mm]),
    ]

    if m.get("uc") == "uc1":
        story += [
            p("UC1 LLM-only vs End-to-end", h2_style),
            table([
                ["Scope", "Latency mean / p50 / p95", "TTFT mean / p50 / p95", "TPOT mean / p50 / p95"],
                ["End-to-end incl. retrieval", f"{fmt_seconds(m['latency']['mean'])} / {fmt_seconds(m['latency']['p50'])} / {fmt_seconds(m['latency']['p95'])}", f"{fmt_seconds(m['ttft']['mean'])} / {fmt_seconds(m['ttft']['p50'])} / {fmt_seconds(m['ttft']['p95'])}", f"{fmt_value(m['tpot']['mean'])} / {fmt_value(m['tpot']['p50'])} / {fmt_value(m['tpot']['p95'])}"],
                ["LLM-only", "N/A" if not m.get("has_uc1_llm_metrics") else f"{fmt_seconds(m['uc1_llm_latency']['mean'])} / {fmt_seconds(m['uc1_llm_latency']['p50'])} / {fmt_seconds(m['uc1_llm_latency']['p95'])}", "N/A" if not m.get("has_uc1_llm_metrics") else f"{fmt_seconds(m['uc1_llm_ttft']['mean'])} / {fmt_seconds(m['uc1_llm_ttft']['p50'])} / {fmt_seconds(m['uc1_llm_ttft']['p95'])}", "N/A" if not m.get("has_uc1_llm_metrics") else f"{fmt_value(m['uc1_llm_tpot']['mean'])} / {fmt_value(m['uc1_llm_tpot']['p50'])} / {fmt_value(m['uc1_llm_tpot']['p95'])}"],
            ]),
        ]

    story += [
        p("Concurrency Summary", h2_style),
        table(
            [["Run", "Concurrency", "Requests", "Completed", "Errors", "Error rate", "RPM", "TPM", m["throughput_label"], "Latency P50/P95", "TTFT P50/P95", "TPOT P50/P95"]]
            + [[row.get("run_index"), row.get("concurrency"), row.get("requests"), row.get("completed"), row.get("errors"), row.get("error_rate"), row.get("rpm"), row.get("tpm"), f"{(row.get('rpm') or 0) * 60:.2f}" if m.get("uc") == "uc2" else row.get("rpm"), f"{fmt_seconds(row.get('latency_p50_ms'))} / {fmt_seconds(row.get('latency_p95_ms'))}", f"{fmt_seconds(row.get('ttft_p50_ms'))} / {fmt_seconds(row.get('ttft_p95_ms'))}", f"{row.get('tpot_p50_ms') or 'N/A'} / {row.get('tpot_p95_ms') or 'N/A'}"] for row in m.get("summary_rows", [])],
        ),
    ]

    if m.get("agent_breakdown"):
        story += [p("UC2 Agent Metrics", h2_style)]
        story.append(table(
            [["Agent", "Calls", "Completed", "Errors", "Latency P50/P95", "TTFT P50/P95", "TPOT P50/P95", "Input tokens sum/P50/P95", "Output tokens sum/P50/P95", "Total tokens sum/P50/P95"]]
            + [[
                a["agent"],
                a["calls"],
                a["completed"],
                a["errors"],
                f"{fmt_seconds(a['latency']['p50'])} / {fmt_seconds(a['latency']['p95'])}",
                f"{fmt_seconds(a['ttft']['p50'])} / {fmt_seconds(a['ttft']['p95'])}",
                f"{a['tpot']['p50'] or 'N/A'} / {a['tpot']['p95'] or 'N/A'}",
                fmt_token_triplet(a["input_tokens"]),
                fmt_token_triplet(a["output_tokens"]),
                fmt_token_triplet(a["total_tokens"]),
            ] for a in m["agent_breakdown"]],
            [28 * mm, 14 * mm, 18 * mm, 14 * mm, 31 * mm, 31 * mm, 27 * mm, 38 * mm, 38 * mm, 38 * mm],
        ))

    story += [
        p("Fairness & Disclosure", h2_style),
        table([
            ["SLA compliance", m["sla_status"]],
            ["Network RTT", m["network_rtt"]],
            ["Test window", f"{started_label} - {finished_label}. {m['test_window']}"],
            ["Token source", "Server usage field when available; missing fields are shown as 0/N/A."],
        ], [45 * mm, 180 * mm]),
    ]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=10 * mm, leftMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm, title=f"Benchmark Report {job_id}")

    def draw_platform_watermark(canvas: Any, _doc: Any) -> None:
        page_width, page_height = landscape(A4)
        canvas.saveState()
        try:
            canvas.setFillAlpha(0.08)
        except Exception:
            pass
        canvas.setFillColor(colors.HexColor("#9ca3af"))
        canvas.setFont(font_name, 58)
        canvas.translate(page_width / 2, page_height / 2)
        canvas.rotate(24)
        canvas.drawCentredString(0, 0, platform_label)
        canvas.restoreState()

        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.setFont(font_name, 9)
        canvas.drawRightString(page_width - 10 * mm, page_height - 7 * mm, f"PLATFORM: {platform_label}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_platform_watermark, onLaterPages=draw_platform_watermark)
    return buffer.getvalue()


def qdrant_headers(config: dict[str, Any]) -> dict[str, str]:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from config_utils import auth_headers

    return auth_headers(get_path(config, "qdrant.api_key"), get_path(config, "qdrant.username"), get_path(config, "qdrant.password"))


def qdrant_request(config: dict[str, Any], method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from config_utils import http_json

    base = str(get_path(config, "qdrant.url")).rstrip("/")
    return http_json(method, base + path, payload, qdrant_headers(config), timeout=int(get_path(config, "runtime.timeout_seconds", 120)))


def parse_scroll_offset(value: str) -> str | int | None:
    if value == "":
        return None
    return int(value) if value.isdigit() else value


def encode_cursor_history(values: list[str]) -> str:
    if not values:
        return ""
    raw = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor_history(value: str) -> list[str]:
    if not value:
        return []
    try:
        padded = value + "=" * (-len(value) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        return [str(item) for item in data] if isinstance(data, list) else []
    except Exception:
        return []


@app.on_event("startup")
def startup() -> None:
    ensure_default_dataset()
    if not PRICING_FILE.exists():
        write_json(PRICING_FILE, {"input_per_1m": 0.0, "output_per_1m": 0.0, "currency": "USD"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/") -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {
        "next": next,
        "error": request.query_params.get("error", ""),
        "show_default_hint": not CONFIG_LOCAL.exists(),
    })


@app.post("/api/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/")) -> RedirectResponse:
    config = load_effective_config()
    expected_user = str(get_path(config, "web.username", "admin"))
    expected_password = str(get_path(config, "web.password", "admin"))
    if username != expected_user or password != expected_password:
        return RedirectResponse("/login?error=Invalid%20username%20or%20password", status_code=303)
    response = RedirectResponse(next or "/", status_code=303)
    response.set_cookie("benchmark_session", sign_session(username), httponly=True, samesite="lax")
    return response


@app.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("benchmark_session")
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    reports = load_report_index()[:5]
    return templates.TemplateResponse(request, "index.html", {"datasets": list_datasets(), "config_ready": local_config_ready(), "reports": reports, "jobs": list_jobs(5)})


@app.get("/datasets", response_class=HTMLResponse)
def datasets_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "datasets.html", {"datasets": list_datasets(), "config_ready": local_config_ready()})


@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), name: str = Form("")) -> RedirectResponse:
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    dataset_id = f"ds_{int(time.time())}"
    upload_path = WEB_DATA / f"{dataset_id}.zip"
    with upload_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        normalize_uploaded_zip(upload_path, dataset_id, name or file.filename)
    finally:
        upload_path.unlink(missing_ok=True)
    return RedirectResponse(f"/datasets/{dataset_id}", status_code=303)


@app.post("/api/datasets/delete")
async def delete_selected_datasets(request: Request) -> RedirectResponse:
    form = await request.form()
    delete_datasets([str(value) for value in form.getlist("dataset_ids")])
    return RedirectResponse("/datasets", status_code=303)


@app.get("/datasets/{dataset_id}", response_class=HTMLResponse)
def dataset_detail(request: Request, dataset_id: str) -> HTMLResponse:
    meta = read_json(dataset_meta_path(dataset_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="dataset not found")
    return templates.TemplateResponse(request, "dataset_detail.html", {"dataset": meta, "config_ready": local_config_ready(), "config_errors": validate_local_config()})


@app.post("/api/datasets/{dataset_id}/delete")
def delete_dataset(dataset_id: str) -> RedirectResponse:
    delete_datasets([dataset_id])
    return RedirectResponse("/datasets", status_code=303)


@app.post("/api/datasets/{dataset_id}/init-qdrant")
def init_qdrant(dataset_id: str, mode: str = Form("incremental"), batch_size: int = Form(10)) -> RedirectResponse:
    meta = read_json(dataset_meta_path(dataset_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="dataset not found")
    config_errors = validate_local_config()
    if config_errors:
        return RedirectResponse("/settings/config?error=Please%20complete%20configuration%20first", status_code=303)
    config_path = CONFIG_LOCAL
    job_id = new_job_id("qdrant")
    event_log = JOBS_DIR / f"{job_id}_events.jsonl"
    cmd = [sys.executable, str(SCRIPTS_DIR / "build_qdrant_index.py"), "--config", str(config_path.relative_to(ROOT)), "--data-dir", str(Path(meta["data_dir"]).resolve()), "--batch-size", str(batch_size), "--event-log", str(event_log)]
    if mode == "overwrite":
        cmd.append("--recreate-collection")
    job = {"job_id": job_id, "kind": "qdrant_init", "dataset_id": dataset_id, "config": CONFIG_LOCAL.name, "mode": mode, "status": "queued", "created_at": now_iso(), "event_log_path": str(event_log)}
    save_job(job)
    thread = threading.Thread(target=run_subprocess_job, args=(job, cmd), daemon=True)
    thread.start()
    meta["qdrant"] = {"last_job_id": job_id, "mode": mode, "config": CONFIG_LOCAL.name, "started_at": now_iso()}
    write_json(dataset_meta_path(dataset_id), meta)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.get("/qdrant", response_class=HTMLResponse)
def qdrant_page(request: Request, article_id: str = "", product: str = "", category: str = "", topic_id: str = "", limit: int = 20, offset: str = "", page: int = 1, history: str = "") -> HTMLResponse:
    points: list[dict[str, Any]] = []
    error_text = ""
    collection = ""
    limit = min(max(int(limit or 20), 1), 100)
    page = max(int(page or 1), 1)
    history_values = decode_cursor_history(history)
    next_offset = ""
    if not local_config_ready():
        error_text = pick_text(
            request,
            "Please complete Settings before browsing the knowledge index.",
            "请先完成系统配置，再浏览知识库索引。",
            "กรุณาตั้งค่าระบบให้เสร็จก่อนเรียกดูดัชนีความรู้",
        )
    else:
        try:
            config = load_config_yaml(CONFIG_LOCAL)
            collection = get_path(config, "qdrant.collection_name", "")
            if not collection:
                raise ValueError("missing collection")
            quoted_collection = quote(str(collection), safe="")
            try:
                qdrant_request(config, "GET", f"/collections/{quoted_collection}")
            except Exception as exc:
                if "doesn't exist" in str(exc) or "not found" in str(exc).lower() or "HTTP 404" in str(exc):
                    error_text = pick_text(
                        request,
                        f"Knowledge index collection '{collection}' does not exist. Initialize a dataset from Datasets, or set Collection name in Settings to an existing Qdrant collection.",
                        f"知识库索引集合 '{collection}' 不存在。请在数据集页面初始化索引，或在设置页把集合名称改为已有的 Qdrant 集合。",
                        f"ไม่พบ collection ดัชนีความรู้ '{collection}' กรุณาเริ่มต้นดัชนีจากหน้า Datasets หรือตั้งชื่อ collection ใน Settings ให้ตรงกับ Qdrant",
                    )
                    raise LookupError("collection missing") from exc
                raise
            must = []
            for key, value in [("article_id", article_id), ("product", product), ("category", category), ("topic_id", topic_id)]:
                if value:
                    must.append({"key": key, "match": {"value": value}})
            payload: dict[str, Any] = {"limit": limit, "with_payload": True, "with_vector": False}
            parsed_offset = parse_scroll_offset(offset)
            if parsed_offset is not None:
                payload["offset"] = parsed_offset
            if must:
                payload["filter"] = {"must": must}
            resp = qdrant_request(config, "POST", f"/collections/{quoted_collection}/points/scroll", payload)
            result = resp.get("result", {})
            points = result.get("points", [])
            if result.get("next_page_offset") is not None:
                next_offset = str(result.get("next_page_offset"))
        except LookupError:
            points = []
        except ValueError:
            error_text = pick_text(
                request,
                "Collection name is empty. Please set it in Settings.",
                "集合名称为空，请先在设置页填写。",
                "ชื่อ collection ว่าง กรุณาตั้งค่าใน Settings",
            )
        except Exception as exc:
            error_text = pick_text(
                request,
                f"Could not read Qdrant. Please check the Qdrant URL, credentials, and service status. Detail: {exc}",
                f"无法读取 Qdrant。请检查 Qdrant 地址、凭据和服务状态。详情：{exc}",
                f"ไม่สามารถอ่าน Qdrant ได้ กรุณาตรวจสอบ URL, credentials และสถานะบริการ รายละเอียด: {exc}",
            )
    prev_offset = history_values[-1] if history_values else ""
    prev_history = encode_cursor_history(history_values[:-1])
    next_history = encode_cursor_history(history_values + [offset])
    return templates.TemplateResponse(request, "qdrant.html", {
        "collection": collection,
        "points": points,
        "error": error_text,
        "filters": {"article_id": article_id, "product": product, "category": category, "topic_id": topic_id, "limit": limit},
        "pager": {
            "page": page,
            "offset": offset,
            "history": history,
            "prev_offset": prev_offset,
            "prev_history": prev_history,
            "next_offset": next_offset,
            "next_history": next_history,
            "has_prev": bool(history_values),
            "has_next": bool(next_offset),
        },
    })


@app.get("/run", response_class=HTMLResponse)
def run_page(request: Request) -> HTMLResponse:
    return RedirectResponse("/uc1", status_code=303)


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request, status: str = "", kind: str = "", uc: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "jobs.html", {
        "jobs": list_jobs(status=status, kind=kind, uc=uc),
        "filters": {"status": status, "kind": kind, "uc": uc},
    })


@app.post("/api/jobs/delete")
async def delete_selected_jobs(request: Request) -> RedirectResponse:
    form = await request.form()
    delete_jobs([str(value) for value in form.getlist("job_ids")])
    return RedirectResponse("/jobs", status_code=303)


def uc_defaults(uc: str) -> dict[str, Any]:
    flow = [{"id": sid, "label": label, "zh": zh, "status": "pending", "duration_text": "", "type": stage_type(sid)} for sid, label, zh in UC_FLOW_STAGES[uc]]
    flow_lookup = {stage["id"]: stage for stage in flow}
    uc2_parallel = None
    if uc == "uc2":
        uc2_parallel = {
            "entry": flow_lookup.get("load_transcript"),
            "specialists": [flow_lookup[sid] for sid in ["summary", "sentiment", "compliance", "qa_score", "intent_outcome"] if sid in flow_lookup],
            "account_branch": [flow_lookup[sid] for sid in ["account_tool_call", "account_lookup", "account_context"] if sid in flow_lookup],
            "final": flow_lookup.get("synthesizer"),
            "post": [flow_lookup[sid] for sid in ["record_metrics", "report"] if sid in flow_lookup],
        }
    return {
        "uc": uc,
        "datasets": list_datasets(),
        "config_ready": local_config_ready(),
        "config_errors": validate_local_config(),
        "title": "FAQ QA Bot Test" if uc == "uc1" else "Call Insight Analytics Test",
        "title_zh": "智能问答测试" if uc == "uc1" else "呼叫洞察测试",
        "description": "Validate whether the assistant can answer customer questions from approved knowledge base evidence." if uc == "uc1" else "Validate whether multi-agent analysis can summarize calls, check compliance, score quality, and combine account context.",
        "description_zh": "验证助手是否能基于已批准知识库证据回答客户问题。" if uc == "uc1" else "验证多 Agent 是否能完成通话摘要、合规检查、质检评分并结合账户上下文。",
        "flow": flow,
        "flow_layout": "uc2_parallel" if uc == "uc2" else "linear",
        "uc2_parallel": uc2_parallel,
    }


@app.get("/uc1", response_class=HTMLResponse)
def uc1_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "uc_test.html", uc_defaults("uc1"))


@app.get("/uc2", response_class=HTMLResponse)
def uc2_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "uc_test.html", uc_defaults("uc2"))


def preset_values(uc: str, test_size: str, load_level: str, custom_limit: int, custom_concurrency: str, custom_runs: int) -> tuple[int, str, int]:
    if test_size not in {"smoke", "standard", "full"}:
        test_size = "smoke"
    size_defaults = {
        "smoke": 5 if uc == "uc1" else 3,
        "standard": 20 if uc == "uc1" else 10,
        "full": 0,
    }
    load_defaults = {
        "single": ("1", 1),
        "moderate": ("4", 1),
        "high": ("16", 1),
        "sweep": ("1,4,16,64", 1),
        "custom": (custom_concurrency, custom_runs),
    }
    concurrency, runs = load_defaults.get(load_level, ("1", 1))
    return int(size_defaults.get(test_size, 5)), concurrency, int(runs)


@app.post("/api/jobs/start")
def start_job(
    uc: str = Form(...),
    dataset_id: str = Form(...),
    test_size: str = Form("smoke"),
    load_level: str = Form("single"),
    custom_limit: int = Form(5),
    custom_concurrency_levels: str = Form("1"),
    custom_runs_per_platform: int = Form(1),
    timeout_seconds: int = Form(120),
    dry_run: str | None = Form(None),
    no_stream: str | None = Form(None),
    no_reranker: str | None = Form(None),
) -> RedirectResponse:
    if uc not in {"uc1", "uc2"}:
        raise HTTPException(status_code=400, detail="uc must be uc1 or uc2")
    if test_size not in {"smoke", "standard", "full"}:
        test_size = "smoke"
    meta = read_json(dataset_meta_path(dataset_id), None)
    if not meta:
        raise HTTPException(status_code=400, detail="dataset not found")
    config_errors = validate_local_config()
    if config_errors:
        return RedirectResponse("/settings/config?error=Please%20complete%20configuration%20first", status_code=303)
    config_path = CONFIG_LOCAL
    config = load_config_yaml(config_path)
    platform_label = str(get_path(config, "runtime.platform_label", "platform") or "platform")
    job_id = new_job_id(uc)
    event_log = JOBS_DIR / f"{job_id}_events.jsonl"
    script = "run_uc1_rag.py" if uc == "uc1" else "run_uc2_agents.py"
    limit, concurrency_levels, runs_per_platform = preset_values(uc, test_size, load_level, custom_limit, custom_concurrency_levels, custom_runs_per_platform)
    cmd = [sys.executable, str(SCRIPTS_DIR / script), "--config", str(config_path.relative_to(ROOT)), "--data-dir", str(Path(meta["data_dir"]).resolve()), "--concurrency-levels", concurrency_levels, "--runs-per-platform", str(runs_per_platform), "--timeout-seconds", str(timeout_seconds)]
    cmd += ["--event-log", str(event_log)]
    if limit > 0:
        cmd += ["--limit", str(limit)]
    if dry_run:
        cmd.append("--dry-run")
    if no_stream:
        cmd.append("--no-stream")
    if uc == "uc1" and no_reranker:
        cmd.append("--no-reranker")
    pricing = load_pricing()
    job = {"job_id": job_id, "kind": "uc_run", "uc": uc, "dataset_id": dataset_id, "config": CONFIG_LOCAL.name, "platform_label": platform_label, "status": "queued", "created_at": now_iso(), "event_log_path": str(event_log), "params": {"test_size": test_size, "load_level": load_level, "limit": limit, "concurrency_levels": concurrency_levels, "runs_per_platform": runs_per_platform, "timeout_seconds": timeout_seconds, "dry_run": bool(dry_run), "no_stream": bool(no_stream), "no_reranker": bool(no_reranker), "platform_label": platform_label}, "pricing": pricing}
    save_job(job)
    thread = threading.Thread(target=run_subprocess_job, args=(job, cmd), daemon=True)
    thread.start()
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str) -> HTMLResponse:
    job = load_job(job_id)
    if job.get("kind") == "qdrant_init":
        template = "job_import.html"
    elif job.get("uc") == "uc2":
        template = "job_uc2.html"
    else:
        template = "job_uc1.html"
    return templates.TemplateResponse(request, template, {"job": job, "flow": build_flow_state(job), "platform_label": infer_platform_label(job)})


@app.get("/api/jobs/{job_id}/status", response_class=HTMLResponse)
def job_status_fragment(request: Request, job_id: str, selected_channel: str = "", selected_channel_slot: int = 0) -> HTMLResponse:
    job = load_job(job_id)
    log = tail_text(Path(job["log_path"]) if job.get("log_path") else None)
    template = "partials/job_status_import.html" if job.get("kind") == "qdrant_init" else "partials/job_status.html"
    channel_id = selected_channel or request.headers.get("x-selected-channel", "")
    try:
        channel_slot = selected_channel_slot or int(request.headers.get("x-selected-channel-slot", "0") or 0)
    except ValueError:
        channel_slot = 0
    return templates.TemplateResponse(request, template, {"job": job, "log": log, "flow": build_flow_state(job, channel_id, channel_slot), "platform_label": infer_platform_label(job)})


@app.post("/api/jobs/{job_id}/stop")
def stop_job(job_id: str) -> RedirectResponse:
    job = load_job(job_id)
    if job.get("status") in {"completed", "failed", "stopped"}:
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)
    job["stop_requested"] = True
    job["stop_requested_at"] = now_iso()
    job["stop_message"] = "Stop requested by operator / 操作员请求停止"
    pid = int(job.get("process_group_id") or job.get("pid") or 0)
    if pid:
        job["status"] = "stopping"
        save_job(job)
        request_stop_process(pid)
    else:
        job["status"] = "stopped"
        job["finished_at"] = now_iso()
        job["return_code"] = None
        save_job(job)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/api/jobs/{job_id}/delete")
def delete_job(job_id: str) -> RedirectResponse:
    delete_jobs([job_id])
    return RedirectResponse("/jobs", status_code=303)


@app.get("/api/jobs/{job_id}/log-tail")
def job_log_tail(job_id: str) -> dict[str, str]:
    job = load_job(job_id)
    return {"log": tail_text(Path(job["log_path"]) if job.get("log_path") else None)}


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, uc: str = "", status: str = "") -> HTMLResponse:
    rows = load_report_index()
    if uc:
        rows = [row for row in rows if row.get("uc") == uc]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return templates.TemplateResponse(request, "reports.html", {"reports": rows, "filters": {"uc": uc, "status": status}})


@app.post("/api/reports/delete")
async def delete_selected_reports(request: Request) -> RedirectResponse:
    form = await request.form()
    delete_reports([str(value) for value in form.getlist("job_ids")])
    return RedirectResponse("/reports", status_code=303)


@app.get("/reports/{job_id}", response_class=HTMLResponse)
def report_detail(request: Request, job_id: str) -> HTMLResponse:
    report = report_lookup(job_id)
    raw_path = Path(report["raw_log_path"]) if report.get("raw_log_path") else None
    summary_path = Path(report["summary_path"]) if report.get("summary_path") else None
    pricing = load_pricing()
    data = summarize_report(raw_path, summary_path, pricing)
    return templates.TemplateResponse(request, "report_detail.html", {"report": report, "data": data, "platform_label": infer_platform_label(report)})


@app.get("/reports/{job_id}/pdf")
def report_pdf(job_id: str, tz: str = Query("")) -> Response:
    report = report_lookup(job_id)
    raw_path = Path(report["raw_log_path"]) if report.get("raw_log_path") else None
    summary_path = Path(report["summary_path"]) if report.get("summary_path") else None
    pricing = load_pricing()
    data = summarize_report(raw_path, summary_path, pricing)
    pdf = generate_report_pdf(job_id, report, data, tz)
    filename = report_pdf_filename(report, data, tz_name=tz)
    fallback_filename = report_pdf_filename(report, data, ascii_only=True, tz_name=tz)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{fallback_filename}\"; filename*=UTF-8''{quote(filename)}"},
    )


@app.post("/api/reports/{job_id}/delete")
def delete_report(job_id: str) -> RedirectResponse:
    delete_reports([job_id])
    return RedirectResponse("/reports", status_code=303)


@app.get("/api/reports")
def api_reports() -> list[dict[str, Any]]:
    return load_report_index()


@app.get("/api/reports/{job_id}")
def api_report(job_id: str) -> dict[str, Any]:
    reports = load_report_index()
    report = next((row for row in reports if row.get("job_id") == job_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    raw_path = Path(report["raw_log_path"]) if report.get("raw_log_path") else None
    summary_path = Path(report["summary_path"]) if report.get("summary_path") else None
    return {"report": report, "data": summarize_report(raw_path, summary_path, load_pricing())}


@app.get("/settings/config", response_class=HTMLResponse)
def config_page(request: Request) -> HTMLResponse:
    config = load_effective_config()
    errors = validate_local_config()
    return templates.TemplateResponse(request, "settings_config.html", {
        "sections": config_form_sections(config),
        "source": effective_config_path().name,
        "config_exists": CONFIG_LOCAL.exists(),
        "errors": errors,
        "saved": request.query_params.get("saved", ""),
        "error": request.query_params.get("error", ""),
        "pricing": load_pricing(),
    })


@app.post("/settings/config")
@app.post("/api/config")
async def save_config(request: Request) -> RedirectResponse:
    try:
        form = dict(await request.form())
        save_config_from_form(form)
        save_pricing_values({
            "input_per_1m": float(form.get("pricing.input_per_1m") or 0),
            "output_per_1m": float(form.get("pricing.output_per_1m") or 0),
            "currency": form.get("pricing.currency") or "USD",
        })
    except Exception as exc:
        return RedirectResponse(f"/settings/config?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/settings/config?saved=1", status_code=303)


@app.get("/settings/pricing", response_class=HTMLResponse)
def pricing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "pricing.html", {"pricing": load_pricing()})


@app.post("/api/pricing")
def save_pricing(input_per_1m: float = Form(0.0), output_per_1m: float = Form(0.0), currency: str = Form("USD")) -> RedirectResponse:
    save_pricing_values({"input_per_1m": input_per_1m, "output_per_1m": output_per_1m, "currency": currency})
    return RedirectResponse("/settings/pricing", status_code=303)

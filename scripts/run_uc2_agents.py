#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from benchmark_utils import EventLogger, call_chat_completion, parse_int_list, run_concurrency_sweep
from config_utils import add_common_args, get_path, load_config, validate_config


ROOT = Path(__file__).resolve().parents[1]


def preview_text(value: Any, limit: int = 1800) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value or "")
    text = text.strip()
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
            uc="uc2",
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


AGENTS = [
    ("summary", "Summarize the call in concise Thai with key facts and next steps."),
    ("sentiment", "Assess customer sentiment and evidence from the transcript."),
    ("compliance", "Check disclosures, privacy handling, collection tone, and prohibited secret requests."),
    ("qa_score", "Score agent quality from 1-5 and explain defects."),
    ("intent_outcome", "Extract customer intent, outcome, and unresolved items."),
]

AGENT_STAGE_LABELS = {
    "summary": "Summary Agent / 摘要分析",
    "sentiment": "Sentiment Agent / 情绪分析",
    "compliance": "Compliance Agent / 合规检查",
    "qa_score": "QA Score Agent / 质检评分",
    "intent_outcome": "Intent Agent / 意图与结果",
    "account_tool_call": "Account Tool Call Agent / 账户工具调用",
    "account_lookup": "Account Lookup / 查询账户摘要",
    "account_context": "Account Context Agent / 账户上下文",
    "synthesizer": "Final Insight / 汇总洞察",
    "record_metrics": "Record benchmark metrics / 记录测试指标",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def get_account_summary(customer_id: str, accounts_by_customer: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return accounts_by_customer[customer_id]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run UC2 fixed multi-agent call insight benchmark")
    add_common_args(parser)
    parser.add_argument("--data-dir", default="benchmark_data")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency-levels", help="Comma-separated override, for example: 1 or 1,4")
    parser.add_argument("--runs-per-platform", type=int, help="Override runtime.runs_per_platform")
    parser.add_argument("--timeout-seconds", type=int, help="Override runtime.timeout_seconds")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming chat completions for this run")
    parser.add_argument("--event-log", help="Optional JSONL event log for the web UI")
    args = parser.parse_args()
    events = EventLogger(args.event_log)
    events.emit("job_started", uc="uc2", stage="load_transcript", message="Load call transcripts / 读取通话记录")

    config = load_config(args.config)
    if args.timeout_seconds:
        config["runtime"]["timeout_seconds"] = args.timeout_seconds
    if args.no_stream:
        config["runtime"]["stream"] = False
    problems = validate_config(config, allow_placeholders=args.allow_example_placeholders or args.dry_run)
    if problems:
        events.emit("stage_error", uc="uc2", stage="validate_config", message="\n".join(problems))
        raise SystemExit("\n".join(f"CONFIG ERROR: {p}" for p in problems))

    transcripts = read_jsonl(ROOT / args.data_dir / "uc2" / "transcripts.jsonl")
    accounts = read_jsonl(ROOT / args.data_dir / "uc2" / "account_lookup.jsonl")
    accounts_by_customer = {row["customer_id"]: row for row in accounts}
    if args.limit:
        transcripts = transcripts[:args.limit]
    events.emit("stage_done", uc="uc2", stage="load_transcript", total=len(transcripts), message="Transcripts ready / 通话记录已准备")

    out_dir = ROOT / str(get_path(config, "runtime.output_dir")) / str(get_path(config, "runtime.platform_label", "platform")) / "uc2"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    raw_path = out_dir / f"uc2_raw_logs_{stamp}.jsonl"
    summary_path = out_dir / f"uc2_summary_{stamp}.json"

    def mock_call(agent: str) -> dict[str, Any]:
        return {
            "agent": agent,
            "mode": "dry-run",
            "status": "ok",
            "latency_ms": 0.0,
            "ttft_ms": 0.0,
            "tpot_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "content": f"MOCK_{agent}_OUTPUT",
        }

    def normalize_call(agent: str, llm: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": agent,
            "status": llm["status"],
            "error": llm["error"],
            "latency_ms": llm["latency_ms"],
            "ttft_ms": llm["ttft_ms"],
            "tpot_ms": llm["tpot_ms"],
            "input_tokens": llm["input_tokens"],
            "output_tokens": llm["output_tokens"],
            "total_tokens": llm["total_tokens"],
            "content": llm["content"],
        }

    agent_parallelism = len(AGENTS) + 1

    def run_agent_call(
        name: str,
        prompt: str,
        transcript: dict[str, Any],
        run_index: int,
        concurrency: int,
    ) -> tuple[str, dict[str, Any], str]:
        item_id = transcript["transcript_id"]
        events.emit("stage_started", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage=name, message=AGENT_STAGE_LABELS[name])
        if args.dry_run:
            call = mock_call(name)
        else:
            llm = call_chat_completion(config, [
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript["dialogue"]},
            ], on_delta=make_output_streamer(events, item_id, run_index, concurrency, name))
            call = normalize_call(name, llm)
        events.emit(
            "stage_done",
            uc="uc2",
            item_id=item_id,
            run_index=run_index,
            concurrency=concurrency,
            stage=name,
            status=call.get("status"),
            message=AGENT_STAGE_LABELS[name],
            output_preview=preview_text(call.get("content")),
        )
        return name, call, str(call.get("content") or "")

    def run_account_branch(
        transcript: dict[str, Any],
        run_index: int,
        concurrency: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        item_id = transcript["transcript_id"]
        branch_calls: list[dict[str, Any]] = []
        branch_outputs: dict[str, Any] = {}
        tool_records: list[dict[str, Any]] = []

        expected_tool_call = transcript["expected_tool_call"]
        tool_prompt = (
            "You are the account-context specialist. First emit the required tool call as compact JSON only. "
            "Use exactly this tool name: get_account_summary. Do not answer the customer yet."
        )
        tool_payload = {
            "customer_id": transcript["customer_id"],
            "expected_tool_call": expected_tool_call,
            "transcript": transcript["dialogue"],
        }
        events.emit("stage_started", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="account_tool_call", message=AGENT_STAGE_LABELS["account_tool_call"])
        if args.dry_run:
            tool_call = mock_call("account_tool_call")
            tool_call["content"] = json.dumps(expected_tool_call, ensure_ascii=False)
        else:
            llm = call_chat_completion(config, [
                {"role": "system", "content": tool_prompt},
                {"role": "user", "content": json.dumps(tool_payload, ensure_ascii=False)},
            ], on_delta=make_output_streamer(events, item_id, run_index, concurrency, "account_tool_call"))
            tool_call = normalize_call("account_tool_call", llm)
        branch_calls.append(tool_call)
        branch_outputs["account_tool_call"] = tool_call["content"]
        events.emit(
            "stage_done",
            uc="uc2",
            item_id=item_id,
            run_index=run_index,
            concurrency=concurrency,
            stage="account_tool_call",
            status=tool_call.get("status"),
            message=AGENT_STAGE_LABELS["account_tool_call"],
            output_preview=preview_text(tool_call.get("content")),
        )

        account_lookup_started = time.time()
        account = get_account_summary(transcript["customer_id"], accounts_by_customer)
        tool_record = {
            "tool": "get_account_summary",
            "status": "ok",
            "arguments": {"customer_id": transcript["customer_id"]},
            "latency_ms": round((time.time() - account_lookup_started) * 1000, 2),
            "result": account,
        }
        tool_records.append(tool_record)
        events.emit(
            "stage_done",
            uc="uc2",
            item_id=item_id,
            run_index=run_index,
            concurrency=concurrency,
            stage="account_lookup",
            status="ok",
            message=AGENT_STAGE_LABELS["account_lookup"],
            output_preview=preview_text(tool_record),
        )

        events.emit("stage_started", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="account_context", message=AGENT_STAGE_LABELS["account_context"])
        if args.dry_run:
            context_call = mock_call("account_context")
        else:
            llm = call_chat_completion(config, [
                {"role": "system", "content": "Use the mocked account summary to explain account context. Do not invent backend data."},
                {"role": "user", "content": json.dumps({
                    "transcript": transcript["dialogue"],
                    "tool_call": tool_call.get("content"),
                    "account_summary": account,
                }, ensure_ascii=False)},
            ], on_delta=make_output_streamer(events, item_id, run_index, concurrency, "account_context"))
            context_call = normalize_call("account_context", llm)
        branch_calls.append(context_call)
        branch_outputs["account_context"] = context_call["content"]
        events.emit(
            "stage_done",
            uc="uc2",
            item_id=item_id,
            run_index=run_index,
            concurrency=concurrency,
            stage="account_context",
            status=context_call.get("status"),
            message=AGENT_STAGE_LABELS["account_context"],
            output_preview=preview_text(context_call.get("content")),
        )
        return branch_calls, branch_outputs, tool_records

    def worker(transcript: dict[str, Any], run_index: int, concurrency: int) -> dict[str, Any]:
        started = time.time()
        calls: list[dict[str, Any]] = []
        outputs: dict[str, Any] = {}
        tool_calls: list[dict[str, Any]] = []
        item_id = transcript["transcript_id"]
        events.emit("request_started", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="load_transcript", message="Start call insight case / 开始呼叫洞察案例")
        try:
            with ThreadPoolExecutor(max_workers=agent_parallelism) as agent_pool:
                futures = {
                    agent_pool.submit(run_agent_call, name, prompt, transcript, run_index, concurrency): name
                    for name, prompt in AGENTS
                }
                futures[agent_pool.submit(run_account_branch, transcript, run_index, concurrency)] = "account_branch"
                for future in as_completed(futures):
                    branch_name = futures[future]
                    result = future.result()
                    if branch_name == "account_branch":
                        branch_calls, branch_outputs, branch_tool_calls = result
                        calls.extend(branch_calls)
                        outputs.update(branch_outputs)
                        tool_calls.extend(branch_tool_calls)
                        continue
                    name, call, output = result
                    calls.append(call)
                    outputs[name] = output

            events.emit("stage_started", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="synthesizer", message=AGENT_STAGE_LABELS["synthesizer"])
            if args.dry_run:
                call = mock_call("synthesizer")
            else:
                llm = call_chat_completion(config, [
                    {"role": "system", "content": "Synthesize all specialist outputs into one structured call insight report."},
                    {"role": "user", "content": json.dumps(outputs, ensure_ascii=False)},
                ], on_delta=make_output_streamer(events, item_id, run_index, concurrency, "synthesizer"))
                call = normalize_call("synthesizer", llm)
            calls.append(call)
            outputs["synthesizer"] = call["content"]
            events.emit("stage_done", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="synthesizer", status=call.get("status"), message=AGENT_STAGE_LABELS["synthesizer"], output_preview=preview_text(call["content"]))
            status = "ok" if all(call.get("status") in {"ok", None} for call in calls) else "error"
            events.emit("stage_done", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, stage="record_metrics", message=AGENT_STAGE_LABELS["record_metrics"])
            events.emit("request_done", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, status=status, stage="record_metrics", message="Call insight case complete / 呼叫洞察案例完成")
            return {
                "uc": "uc2",
                "run_index": run_index,
                "concurrency": concurrency,
                "transcript_id": transcript["transcript_id"],
                "status": status,
                "latency_ms": round((time.time() - started) * 1000, 2),
                "ttft_ms": min([c["ttft_ms"] for c in calls if c.get("ttft_ms") is not None], default=None),
                "tpot_ms": sum([c["tpot_ms"] for c in calls if c.get("tpot_ms") is not None]) / max(len([c for c in calls if c.get("tpot_ms") is not None]), 1),
                "input_tokens": sum(int(c.get("input_tokens") or 0) for c in calls),
                "output_tokens": sum(int(c.get("output_tokens") or 0) for c in calls),
                "total_tokens": sum(int(c.get("total_tokens") or 0) for c in calls),
                "calls": calls,
                "tool_calls": tool_calls,
                "outputs": outputs,
            }
        except Exception as exc:
            events.emit("request_done", uc="uc2", item_id=item_id, run_index=run_index, concurrency=concurrency, status="error", stage="record_metrics", message=str(exc))
            return {
                "uc": "uc2",
                "run_index": run_index,
                "concurrency": concurrency,
                "transcript_id": transcript["transcript_id"],
                "status": "error",
                "error": str(exc),
                "latency_ms": round((time.time() - started) * 1000, 2),
            }

    levels = parse_int_list(args.concurrency_levels) if args.concurrency_levels else [int(x) for x in get_path(config, "runtime.concurrency_levels", [int(get_path(config, "runtime.concurrency", 1))])]
    runs = args.runs_per_platform if args.runs_per_platform else int(get_path(config, "runtime.runs_per_platform", 1))
    print(f"UC2 plan: transcripts={len(transcripts)}, concurrency_levels={levels}, runs={runs}, llm_calls_per_transcript=8, specialist_branches=6, worker_requests={len(transcripts) * len(levels) * runs}", flush=True)
    events.emit("run_plan", uc="uc2", total_items=len(transcripts), concurrency_levels=levels, runs=runs, llm_calls_per_transcript=8, specialist_branches=6, total_requests=len(transcripts) * len(levels) * runs)
    raw_logs, summaries = run_concurrency_sweep(transcripts, levels, runs, worker)
    with raw_path.open("w", encoding="utf-8") as f:
        for row in raw_logs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary_path.write_text(json.dumps({"uc": "uc2", "summaries": summaries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    events.emit("job_done", uc="uc2", stage="report", status="ok", raw_log_path=str(raw_path), summary_path=str(summary_path), message="UC2 report ready / UC2 报告已生成")
    print(raw_path)
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

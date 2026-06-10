#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable
from urllib import request

from config_utils import auth_headers, get_path, http_json


def parse_int_list(value: str) -> list[int]:
    levels = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not levels or any(level <= 0 for level in levels):
        raise ValueError("value must contain positive integers, for example: 1,4,16")
    return levels


def now_ms() -> float:
    return time.time() * 1000


def percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 2)
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * pct / 100
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return round(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight, 2)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


SPINNER = ["-", "\\", "|", "/"]


class EventLogger:
    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def emit(self, event: str, **payload: Any) -> None:
        if not self.path:
            return
        row = {
            "ts": time.time(),
            "event": event,
            **payload,
        }
        with self.lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_progress(
    run_index: int,
    runs: int,
    concurrency: int,
    done: int,
    total: int,
    started: float,
    ok: int = 0,
    errors: int = 0,
    tick: int = 0,
    final: bool = False,
) -> None:
    total = max(total, 1)
    ratio = min(max(done / total, 0.0), 1.0)
    width = 24
    filled = int(width * ratio)
    bar = "=" * filled + "-" * (width - filled)
    elapsed = time.time() - started
    rate = done / elapsed if elapsed > 0 and done else 0.0
    eta = None if rate <= 0 or done >= total else (total - done) / rate
    active = min(concurrency, max(total - done, 0))
    spinner = SPINNER[tick % len(SPINNER)]
    line = (
        f"\r{spinner} benchmark:run "
        f"run {run_index}/{runs} concurrency={concurrency} "
        f"[{bar}] {ratio * 100:5.1f}% "
        f"{done}/{total} active={active} ok={ok} err={errors} "
        f"{rate:4.2f}req/s elapsed={format_duration(elapsed)} eta={format_duration(eta)}"
    )
    sys.stdout.write(line)
    if final:
        sys.stdout.write("\n")
    sys.stdout.flush()


def call_chat_completion(config: dict[str, Any], messages: list[dict[str, str]], stream: bool | None = None, on_delta: Callable[[str], None] | None = None) -> dict[str, Any]:
    use_stream = bool(get_path(config, "runtime.stream", True) if stream is None else stream)
    url = get_path(config, "llm.base_url").rstrip("/") + "/chat/completions"
    payload = {
        "model": get_path(config, "llm.model"),
        "messages": messages,
        "temperature": float(get_path(config, "runtime.temperature")),
        "max_tokens": int(get_path(config, "runtime.max_tokens")),
        "stream": use_stream,
    }
    headers = auth_headers(get_path(config, "llm.api_key"))
    start = now_ms()
    first_token_ms = None
    output_text_parts: list[str] = []
    usage: dict[str, Any] = {}
    status = "ok"
    error = ""
    if not use_stream:
        try:
            resp = http_json("POST", url, payload, headers, timeout=int(get_path(config, "runtime.timeout_seconds")))
            choices = resp.get("choices") or []
            output = choices[0].get("message", {}).get("content", "") if choices else ""
            usage = resp.get("usage", {})
            first_token_ms = now_ms()
            output_text_parts.append(output)
        except Exception as exc:  # pragma: no cover - live API path
            status = "error"
            error = str(exc)
    else:
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = request.Request(url, data=data, headers=headers, method="POST")
            with request.urlopen(req, timeout=int(get_path(config, "runtime.timeout_seconds"))) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    event = line[5:].strip()
                    if event == "[DONE]":
                        break
                    chunk = json.loads(event)
                    if "usage" in chunk and chunk["usage"]:
                        usage = chunk["usage"]
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        if first_token_ms is None:
                            first_token_ms = now_ms()
                        output_text_parts.append(delta)
                        if on_delta:
                            on_delta(delta)
        except Exception as exc:  # pragma: no cover - live API path
            status = "error"
            error = str(exc)
    end = now_ms()
    output_text = "".join(output_text_parts)
    completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or len(output_text.split())
    ttft_ms = None if first_token_ms is None else round(first_token_ms - start, 2)
    latency_ms = round(end - start, 2)
    tpot_ms = None
    if first_token_ms is not None and completion_tokens and completion_tokens > 1:
        tpot_ms = round((end - first_token_ms) / (completion_tokens - 1), 4)
    return {
        "status": status,
        "error": error,
        "content": output_text,
        "usage": usage,
        "latency_ms": latency_ms,
        "ttft_ms": ttft_ms,
        "tpot_ms": tpot_ms,
        "input_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
        "output_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def run_concurrency_sweep(items: list[Any], levels: list[int], runs: int, worker: Callable[[Any, int, int], dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_logs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for run_index in range(1, runs + 1):
        for concurrency in levels:
            print(f"starting run={run_index}/{runs}, concurrency={concurrency}, requests={len(items)}", flush=True)
            started = time.time()
            level_logs: list[dict[str, Any]] = []
            pool = ThreadPoolExecutor(max_workers=concurrency)
            futures = [pool.submit(worker, item, run_index, concurrency) for item in items]
            pending = set(futures)
            tick = 0
            ok_count = 0
            error_count = 0
            render_progress(run_index, runs, concurrency, 0, len(items), started, ok_count, error_count, tick)
            try:
                while pending:
                    done_futures, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                    if not done_futures:
                        tick += 1
                        render_progress(run_index, runs, concurrency, len(level_logs), len(items), started, ok_count, error_count, tick)
                        continue
                    for future in done_futures:
                        log = future.result()
                        level_logs.append(log)
                        raw_logs.append(log)
                        if log.get("status") == "ok" or log.get("mode") == "dry-run":
                            ok_count += 1
                        else:
                            error_count += 1
                    tick += 1
                    render_progress(run_index, runs, concurrency, len(level_logs), len(items), started, ok_count, error_count, tick, len(level_logs) == len(items))
            except KeyboardInterrupt:
                render_progress(run_index, runs, concurrency, len(level_logs), len(items), started, ok_count, error_count, tick, final=True)
                for future in futures:
                    future.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                pool.shutdown(wait=True)
            elapsed_minutes = max((time.time() - started) / 60, 1e-9)
            ok_logs = [log for log in level_logs if log.get("status") == "ok" or log.get("mode") == "dry-run"]
            latencies = [float(log["latency_ms"]) for log in ok_logs if log.get("latency_ms") is not None]
            ttfts = [float(log["ttft_ms"]) for log in ok_logs if log.get("ttft_ms") is not None]
            tpots = [float(log["tpot_ms"]) for log in ok_logs if log.get("tpot_ms") is not None]
            total_tokens = sum(int(log.get("total_tokens") or 0) for log in ok_logs)
            summaries.append({
                "run_index": run_index,
                "concurrency": concurrency,
                "requests": len(level_logs),
                "completed": len(ok_logs),
                "errors": len(level_logs) - len(ok_logs),
                "error_rate": round((len(level_logs) - len(ok_logs)) / max(len(level_logs), 1), 4),
                "rpm": round(len(ok_logs) / elapsed_minutes, 4),
                "tpm": round(total_tokens / elapsed_minutes, 4),
                "latency_p50_ms": percentile(latencies, 50),
                "latency_p95_ms": percentile(latencies, 95),
                "ttft_p50_ms": percentile(ttfts, 50),
                "ttft_p95_ms": percentile(ttfts, 95),
                "tpot_p50_ms": percentile(tpots, 50),
                "tpot_p95_ms": percentile(tpots, 95),
                "latency_mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
            })
    return raw_logs, summaries

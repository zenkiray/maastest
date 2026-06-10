#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def infer_summary_path(raw_path: Path) -> Path | None:
    name = raw_path.name.replace("_raw_logs_", "_summary_").replace(".jsonl", ".json")
    candidate = raw_path.with_name(name)
    return candidate if candidate.exists() else None


def shorten(value: Any, limit: int = 180) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def ms_to_s(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value) / 1000:.2f}s"
    except (TypeError, ValueError):
        return str(value)


def print_table(rows: list[list[str]], headers: list[str]) -> None:
    table = [headers] + rows
    widths = [max(len(str(row[idx])) for row in table) for idx in range(len(headers))]
    fmt = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * width for width in widths]))
    for row in rows:
        print(fmt.format(*row))


def print_console(raw_path: Path, summary: dict[str, Any] | None, rows: list[dict[str, Any]], max_rows: int) -> None:
    statuses = Counter(row.get("status", "") for row in rows)
    print(f"\nFile: {raw_path}")
    print(f"Records: {len(rows)}")
    print("Status:", ", ".join(f"{key or 'unknown'}={value}" for key, value in statuses.items()))
    if summary:
        print("\nSummary:")
        summary_rows = []
        for item in summary.get("summaries", []):
            summary_rows.append([
                str(item.get("run_index", "")),
                str(item.get("concurrency", "")),
                str(item.get("requests", "")),
                str(item.get("completed", "")),
                str(item.get("errors", "")),
                str(item.get("error_rate", "")),
                ms_to_s(item.get("latency_p50_ms")),
                ms_to_s(item.get("latency_p95_ms")),
                ms_to_s(item.get("ttft_p50_ms")),
                ms_to_s(item.get("ttft_p95_ms")),
                str(item.get("rpm", "")),
                str(item.get("tpm", "")),
            ])
        print_table(summary_rows, ["run", "conc", "req", "ok", "err", "err_rate", "lat_p50", "lat_p95", "ttft_p50", "ttft_p95", "rpm", "tpm"])

    print("\nRequests:")
    request_rows = []
    for row in rows[:max_rows]:
        request_rows.append([
            str(row.get("question_id") or row.get("transcript_id") or ""),
            str(row.get("status", "")),
            ms_to_s(row.get("latency_ms")),
            ms_to_s(row.get("ttft_ms")),
            str(row.get("input_tokens") or ""),
            str(row.get("output_tokens") or ""),
            str(row.get("total_tokens") or ""),
            shorten(row.get("error") or row.get("answer") or row.get("outputs"), 120),
        ])
    print_table(request_rows, ["id", "status", "latency", "ttft", "in_tok", "out_tok", "total", "error_or_answer"])
    if len(rows) > max_rows:
        print(f"\nShowing {max_rows}/{len(rows)} rows. Use --max-rows {len(rows)} to show all.")


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def build_html(raw_path: Path, summary: dict[str, Any] | None, rows: list[dict[str, Any]]) -> str:
    status_counts = Counter(row.get("status", "") for row in rows)
    status_cards = "\n".join(
        f"<div class='metric'><div class='label'>{html_escape(key or 'unknown')}</div><div class='value'>{value}</div></div>"
        for key, value in status_counts.items()
    )
    summary_html = ""
    if summary:
        summary_cells = []
        for item in summary.get("summaries", []):
            summary_cells.append(
                "<tr>"
                f"<td>{html_escape(item.get('run_index'))}</td>"
                f"<td>{html_escape(item.get('concurrency'))}</td>"
                f"<td>{html_escape(item.get('requests'))}</td>"
                f"<td>{html_escape(item.get('completed'))}</td>"
                f"<td>{html_escape(item.get('errors'))}</td>"
                f"<td>{html_escape(item.get('error_rate'))}</td>"
                f"<td>{html_escape(ms_to_s(item.get('latency_p50_ms')))}</td>"
                f"<td>{html_escape(ms_to_s(item.get('latency_p95_ms')))}</td>"
                f"<td>{html_escape(ms_to_s(item.get('ttft_p50_ms')))}</td>"
                f"<td>{html_escape(ms_to_s(item.get('ttft_p95_ms')))}</td>"
                f"<td>{html_escape(item.get('rpm'))}</td>"
                f"<td>{html_escape(item.get('tpm'))}</td>"
                "</tr>"
            )
        summary_html = """
        <h2>Summary</h2>
        <table>
          <thead><tr><th>Run</th><th>Concurrency</th><th>Requests</th><th>OK</th><th>Errors</th><th>Error Rate</th><th>Latency P50</th><th>Latency P95</th><th>TTFT P50</th><th>TTFT P95</th><th>RPM</th><th>TPM</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """.format(rows="\n".join(summary_cells))

    request_rows = []
    for row in rows:
        rid = row.get("question_id") or row.get("transcript_id") or ""
        status = row.get("status", "")
        status_class = "ok" if status == "ok" else "error"
        retrieved = ", ".join(row.get("retrieved") or [])
        detail = row.get("error") or row.get("answer") or json.dumps(row.get("outputs", ""), ensure_ascii=False)
        request_rows.append(
            "<tr>"
            f"<td>{html_escape(rid)}</td>"
            f"<td><span class='badge {status_class}'>{html_escape(status)}</span></td>"
            f"<td>{html_escape(row.get('run_index'))}</td>"
            f"<td>{html_escape(row.get('concurrency'))}</td>"
            f"<td>{html_escape(ms_to_s(row.get('latency_ms')))}</td>"
            f"<td>{html_escape(ms_to_s(row.get('ttft_ms')))}</td>"
            f"<td>{html_escape(ms_to_s(row.get('tpot_ms')))}</td>"
            f"<td>{html_escape(row.get('input_tokens') or '')}</td>"
            f"<td>{html_escape(row.get('output_tokens') or '')}</td>"
            f"<td>{html_escape(row.get('total_tokens') or '')}</td>"
            f"<td>{html_escape(retrieved)}</td>"
            f"<td><details><summary>{html_escape(shorten(detail, 90))}</summary><pre>{html_escape(detail)}</pre></details></td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Benchmark Result - {html_escape(raw_path.name)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; margin: 24px; color: #1f2937; background: #f8fafc; }}
    h1 {{ margin-bottom: 4px; font-size: 24px; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    .subtle {{ color: #64748b; margin-bottom: 18px; }}
    .metrics {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
    .metric {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; min-width: 110px; }}
    .label {{ color: #64748b; font-size: 12px; text-transform: uppercase; }}
    .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #e2e8f0; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px 10px; vertical-align: top; font-size: 13px; }}
    th {{ background: #eef2f7; text-align: left; position: sticky; top: 0; z-index: 1; }}
    tr:hover {{ background: #f8fafc; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; }}
    .badge.ok {{ background: #dcfce7; color: #166534; }}
    .badge.error {{ background: #fee2e2; color: #991b1b; }}
    details summary {{ cursor: pointer; color: #334155; }}
    pre {{ white-space: pre-wrap; max-width: 760px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Benchmark Result</h1>
  <div class="subtle">{html_escape(raw_path)}</div>
  <div class="metrics">
    <div class="metric"><div class="label">Records</div><div class="value">{len(rows)}</div></div>
    {status_cards}
  </div>
  {summary_html}
  <h2>Raw Requests</h2>
  <table>
    <thead><tr><th>ID</th><th>Status</th><th>Run</th><th>Conc</th><th>Latency</th><th>TTFT</th><th>TPOT</th><th>Input</th><th>Output</th><th>Total</th><th>Retrieved</th><th>Detail</th></tr></thead>
    <tbody>{"".join(request_rows)}</tbody>
  </table>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="View benchmark raw JSONL and summary results")
    parser.add_argument("raw_log", help="Path to uc*_raw_logs_*.jsonl")
    parser.add_argument("--summary", help="Optional path to uc*_summary_*.json; inferred by default")
    parser.add_argument("--max-rows", type=int, default=20, help="Max rows to print in console table")
    parser.add_argument("--html", action="store_true", help="Write an HTML report next to the raw log")
    args = parser.parse_args()

    raw_path = Path(args.raw_log)
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path
    summary_path = Path(args.summary) if args.summary else infer_summary_path(raw_path)
    if summary_path and not summary_path.is_absolute():
        summary_path = ROOT / summary_path
    rows = read_jsonl(raw_path)
    summary = read_json(summary_path)
    print_console(raw_path, summary, rows, args.max_rows)
    if args.html:
        report_path = raw_path.with_suffix(".html")
        report_path.write_text(build_html(raw_path, summary, rows), encoding="utf-8")
        print(f"\nHTML report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

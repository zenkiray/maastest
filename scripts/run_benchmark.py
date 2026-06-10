#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def choose(title: str, options: list[tuple[str, str]], default: int = 1) -> int:
    print(f"\n{title}")
    for idx, (label, detail) in enumerate(options, 1):
        suffix = " [default]" if idx == default else ""
        print(f"  {idx}. {label}{suffix}")
        print(f"     {detail}")
    while True:
        try:
            raw = input(f"Select 选择 [{default}]: ").strip()
        except EOFError:
            print("")
            return default
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"Invalid input. Enter 1-{len(options)}, or press Enter for default. 输入无效，请输入 1-{len(options)}，或直接回车使用默认值。")


def ask_positive_int(title: str, default: int) -> int:
    while True:
        raw = input(f"{title} [{default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Invalid input. Enter a positive integer. 输入无效，请输入正整数。")


def list_config_files() -> list[Path]:
    files = sorted(CONFIG_DIR.glob("*.yaml")) + sorted(CONFIG_DIR.glob("*.yml"))
    return [path for path in files if path.is_file()]


def default_config_index(configs: list[Path]) -> int:
    for idx, path in enumerate(configs, 1):
        if path.name == "config.local.yaml":
            return idx
    for idx, path in enumerate(configs, 1):
        if "local" in path.name:
            return idx
    return 1


def choose_config() -> Path:
    configs = list_config_files()
    if not configs:
        raise SystemExit(f"No YAML config files found in {CONFIG_DIR}")
    options = [
        (
            path.name,
            f"Use this config file under config/. 使用 config/ 下的这个配置文件。"
        )
        for path in configs
    ]
    selected = choose("2. Config File 配置文件", options, default_config_index(configs))
    return configs[selected - 1]


def choose_limit(uc: str) -> int:
    default_limit = 5 if uc == "uc1" else 3
    label = "questions" if uc == "uc1" else "transcripts"
    selected = choose(
        f"Limit 限制数量 ({uc.upper()})",
        [
            (f"Smoke test: {default_limit}", f"Run a small real test first. 先跑小样本，降低等待时间和 API 成本。"),
            ("Full dataset: all records", "Use all benchmark records. 跑完整测试集。"),
            ("Custom count", "Enter a custom positive number. 自定义数量。"),
        ],
        1,
    )
    if selected == 1:
        return default_limit
    if selected == 2:
        return 0
    return ask_positive_int(f"How many {label}? 输入要跑多少条", default_limit)


def choose_concurrency_levels() -> str:
    selected = choose(
        "Concurrency Levels 并发档位",
        [
            ("1", "Safest for smoke test and debugging. 最适合小样本排查。"),
            ("1,4", "Small benchmark sweep. 小规模性能测试。"),
            ("1,4,16", "Medium benchmark sweep. 中等规模性能测试。"),
            ("1,4,16,64", "Full customer-style sweep; may be slow and costly. 完整并发扫描，耗时和成本更高。"),
            ("Custom", "Enter comma-separated levels, for example 1,8,32. 自定义并发档位。"),
        ],
        1,
    )
    values = {1: "1", 2: "1,4", 3: "1,4,16", 4: "1,4,16,64"}
    if selected in values:
        return values[selected]
    while True:
        raw = input("Concurrency levels 并发档位 [1,4]: ").strip() or "1,4"
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if parts and all(part.isdigit() and int(part) > 0 for part in parts):
            return ",".join(parts)
        print("Invalid input. Example: 1,4,16. 输入无效，例如：1,4,16。")


def choose_runs() -> int:
    selected = choose(
        "Runs Per Platform 运行轮次",
        [
            ("1", "Single run for smoke test. 单轮测试，适合先验证。"),
            ("2", "Customer-style repeated run. 两轮测试，用于正式对比。"),
            ("Custom", "Enter a custom positive number. 自定义轮次。"),
        ],
        1,
    )
    if selected == 1:
        return 1
    if selected == 2:
        return 2
    return ask_positive_int("Runs per platform 运行轮次", 1)


def common_options() -> dict[str, object]:
    mode = choose(
        "Run Mode 运行模式",
        [
            ("Live API", "Call real LLM/embedding/reranker APIs. 调用真实 API，会产生耗时和费用。"),
            ("Dry run", "No external model calls; verifies flow and output files. 不调用模型 API，只验证流程。"),
        ],
        1,
    )
    stream = choose(
        "Streaming 流式输出",
        [
            ("Use config", "Use runtime.stream from config file. 使用配置文件里的 runtime.stream。"),
            ("Disable streaming", "Send non-streaming chat requests for easier debugging. 关闭流式，便于排查接口兼容问题。"),
        ],
        1,
    )
    timeout = choose(
        "Timeout 超时时间",
        [
            ("Use config", "Use runtime.timeout_seconds from config file. 使用配置文件里的超时时间。"),
            ("60 seconds", "Short timeout for quick failure. 60 秒超时，快速暴露问题。"),
            ("180 seconds", "Longer timeout for slow endpoints. 180 秒超时，适合慢接口。"),
            ("Custom", "Enter a custom timeout in seconds. 自定义秒数。"),
        ],
        1,
    )
    timeout_seconds = None
    if timeout == 2:
        timeout_seconds = 60
    elif timeout == 3:
        timeout_seconds = 180
    elif timeout == 4:
        timeout_seconds = ask_positive_int("Timeout seconds 超时秒数", 120)
    return {
        "dry_run": mode == 2,
        "no_stream": stream == 2,
        "timeout_seconds": timeout_seconds,
    }


def uc1_options() -> dict[str, object]:
    reranker = choose(
        "UC1 Reranker 重排序",
        [
            ("Use config", "Use reranker.enabled and reranker settings from config. 使用配置文件里的重排序设置。"),
            ("Disable reranker", "Skip reranker to isolate embedding/Qdrant/LLM latency. 跳过重排序，便于定位慢点。"),
        ],
        1,
    )
    return {"no_reranker": reranker == 2}


def build_command(script: str, config: Path, limit: int, levels: str, runs: int, opts: dict[str, object], extra: dict[str, object] | None = None) -> list[str]:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / script),
        "--config",
        str(config.relative_to(ROOT)),
        "--concurrency-levels",
        levels,
        "--runs-per-platform",
        str(runs),
    ]
    if limit:
        cmd += ["--limit", str(limit)]
    if opts.get("dry_run"):
        cmd.append("--dry-run")
    if opts.get("no_stream"):
        cmd.append("--no-stream")
    if opts.get("timeout_seconds"):
        cmd += ["--timeout-seconds", str(opts["timeout_seconds"])]
    if extra and extra.get("no_reranker"):
        cmd.append("--no-reranker")
    return cmd


def show_result(raw_log: Path) -> None:
    report_cmd = [sys.executable, str(ROOT / "scripts" / "view_results.py"), str(raw_log)]
    result = subprocess.run(report_cmd, cwd=ROOT, text=True, capture_output=True)
    if result.stdout.strip():
        print(result.stdout)
    if result.stderr.strip():
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"Failed to display result for {raw_log}. 展示结果失败。", file=sys.stderr)


def existing_raw_logs() -> set[Path]:
    return {path.resolve() for path in ROOT.glob("runs/**/uc*_raw_logs_*.jsonl") if path.is_file()}


def run_command(cmd: list[str]) -> int:
    printable = " ".join(cmd)
    print(f"\nCommand 即将执行命令:\n  {printable}\n")
    confirm = choose(
        "Confirm 执行确认",
        [
            ("Run now", "Start the selected benchmark. 立即执行测试。"),
            ("Cancel", "Do not run anything. 取消，不执行。"),
        ],
        1,
    )
    if confirm == 2:
        print("Cancelled. 已取消。")
        return 0
    before = existing_raw_logs()
    result = subprocess.call(cmd, cwd=ROOT)
    if result == 0:
        after = existing_raw_logs()
        raw_logs = sorted(after - before, key=lambda path: path.stat().st_mtime)
        for raw_log in raw_logs:
            show_result(raw_log)
    return result


def main() -> int:
    print("MaaS Synthetic Benchmark Interactive Runner")
    print("MaaS 合成基准测试交互式入口")

    uc_choice = choose(
        "1. Test Case 测试用例",
        [
            ("UC1 RAG QA", "FAQ RAG flow: embed query, Qdrant search, rerank, LLM answer. FAQ 检索问答链路。"),
            ("UC2 Call Insight", "Multi-agent call insight flow; each transcript triggers 8 LLM calls. 通话洞察多智能体链路。"),
            ("UC1 then UC2", "Run both test cases sequentially with the same config. 使用同一配置连续执行两个用例。"),
        ],
        1,
    )
    config = choose_config()
    opts = common_options()
    levels = choose_concurrency_levels()
    runs = choose_runs()

    commands: list[list[str]] = []
    if uc_choice in {1, 3}:
        limit = choose_limit("uc1")
        extra = uc1_options()
        commands.append(build_command("run_uc1_rag.py", config, limit, levels, runs, opts, extra))
    if uc_choice in {2, 3}:
        limit = choose_limit("uc2")
        commands.append(build_command("run_uc2_agents.py", config, limit, levels, runs, opts))

    for cmd in commands:
        result = run_command(cmd)
        if result != 0:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

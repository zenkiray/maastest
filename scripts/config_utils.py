#!/usr/bin/env python3
"""Small YAML/config helpers for the benchmark scripts.

This intentionally supports the simple nested mapping format used by
config/config.example.yaml so the harness does not require PyYAML.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any
from urllib import error, request


REQUIRED_KEYS = [
    "llm.base_url",
    "llm.api_key",
    "llm.model",
    "embedding.base_url",
    "embedding.api_key",
    "embedding.model",
    "embedding.params",
    "reranker.enabled",
    "reranker.base_url",
    "reranker.path",
    "reranker.request_format",
    "reranker.api_key",
    "reranker.model",
    "reranker.params",
    "qdrant.url",
    "qdrant.collection_name",
    "qdrant.api_key",
    "qdrant.username",
    "qdrant.password",
    "runtime.output_dir",
    "runtime.timeout_seconds",
    "runtime.concurrency",
    "runtime.concurrency_levels",
    "runtime.runs_per_platform",
    "runtime.platform_label",
    "runtime.top_k",
    "runtime.rerank_top_n",
    "runtime.max_tokens",
    "runtime.temperature",
    "runtime.qdrant_vector_size",
    "runtime.stream",
    "metrics.record_per_call_logs",
    "metrics.aggregate_percentiles",
    "metrics.record_usage_tokens",
    "metrics.record_ttft_tpot",
    "metrics.record_error_rate",
]


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line_no, raw in enumerate(config_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"{config_path}:{line_no}: indentation must use multiples of two spaces")
        if ":" not in raw:
            raise ValueError(f"{config_path}:{line_no}: expected key: value")
        key, value = raw.strip().split(":", 1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value.strip() == "":
            node: dict[str, Any] = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = _parse_scalar(value)
    return root


def get_path(config: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def validate_config(config: dict[str, Any], allow_placeholders: bool = False) -> list[str]:
    problems: list[str] = []
    for key in REQUIRED_KEYS:
        value = get_path(config, key)
        if value is None:
            problems.append(f"missing required key: {key}")
            continue
        if isinstance(value, str):
            if value == "":
                if key in {"qdrant.api_key", "qdrant.username", "qdrant.password", "llm.organization"}:
                    continue
                problems.append(f"empty required key: {key}")
            if not allow_placeholders and value.startswith("REPLACE_WITH_"):
                problems.append(f"placeholder value must be replaced: {key}")
    if get_path(config, "reranker.enabled") is False:
        problems = [p for p in problems if not p.startswith("placeholder value must be replaced: reranker.")]
    reranker_params = get_path(config, "reranker.params", {})
    if not isinstance(reranker_params, dict):
        problems.append("reranker.params must be a mapping")
    reranker_format = get_path(config, "reranker.request_format")
    if reranker_format not in {"openai", "dashscope"}:
        problems.append("reranker.request_format must be either 'openai' or 'dashscope'")
    embedding_params = get_path(config, "embedding.params", {})
    if not isinstance(embedding_params, dict):
        problems.append("embedding.params must be a mapping")
        embedding_params = {}
    embedding_dimensions = embedding_params.get("dimensions", get_path(config, "embedding.dimensions"))
    qdrant_vector_size = get_path(config, "runtime.qdrant_vector_size")
    if isinstance(embedding_dimensions, int) and embedding_dimensions <= 0:
        problems.append("embedding.params.dimensions must be a positive integer")
    if isinstance(qdrant_vector_size, int) and qdrant_vector_size <= 0:
        problems.append("runtime.qdrant_vector_size must be a positive integer")
    if isinstance(embedding_dimensions, int) and isinstance(qdrant_vector_size, int) and embedding_dimensions != qdrant_vector_size:
        problems.append("embedding.params.dimensions must match runtime.qdrant_vector_size")
    return problems


def auth_headers(api_key: str | None = None, username: str | None = None, password: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["api-key"] = api_key
    elif username and password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def http_json(method: str, url: str, payload: dict[str, Any] | None, headers: dict[str, str], timeout: int = 120) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config/config.local.yaml", help="Path to config YAML")
    parser.add_argument("--allow-example-placeholders", action="store_true", help="Allow placeholder values for validation/dry-run")

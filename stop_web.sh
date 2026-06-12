#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PID_FILE="$ROOT_DIR/web_data/web_runner.pid"
APP_MODULE="web_app.main:app"

info() {
  printf '[web-runner] %s\n' "$*"
}

is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

stop_pid() {
  local pid="$1"
  local label="$2"
  if ! is_running "$pid"; then
    return 1
  fi
  info "stopping ${label} pid=$pid"
  kill "$pid" >/dev/null 2>&1 || true
  for _ in {1..30}; do
    if ! is_running "$pid"; then
      return 0
    fi
    sleep 0.2
  done
  if is_running "$pid"; then
    info "forcing stop for ${label} pid=$pid"
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
}

stopped=0
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && stop_pid "$pid" "web runner"; then
    stopped=1
  fi
  rm -f "$PID_FILE"
fi

extra_pids="$(pgrep -f "uvicorn ${APP_MODULE}" 2>/dev/null || true)"
if [[ -n "$extra_pids" ]]; then
  while IFS= read -r pid; do
    [[ -z "$pid" || "$pid" == "$$" ]] && continue
    if stop_pid "$pid" "orphan web runner"; then
      stopped=1
    fi
  done <<< "$extra_pids"
fi

if [[ "$stopped" == "1" ]]; then
  info "web runner stopped"
else
  info "web runner is not running"
fi

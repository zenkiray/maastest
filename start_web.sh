#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv_web}"
PYTHON_BOOTSTRAP_DIR="${PYTHON_BOOTSTRAP_DIR:-$ROOT_DIR/.python_bootstrap}"
PID_FILE="$ROOT_DIR/web_data/web_runner.pid"
LOG_FILE="$ROOT_DIR/web_data/web_runner.log"
APP_MODULE="web_app.main:app"

mkdir -p "$ROOT_DIR/web_data"

info() {
  printf '[web-runner] %s\n' "$*"
}

is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

python_version_ok() {
  local python_bin="$1"
  "$python_bin" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

python_version_text() {
  local python_bin="$1"
  "$python_bin" - <<'PY' 2>/dev/null || true
import sys
print(".".join(str(part) for part in sys.version_info[:3]))
PY
}

resolve_python() {
  local candidates=()
  if [[ -n "${PYTHON:-}" ]]; then
    candidates+=("$PYTHON")
  else
    candidates+=("$PYTHON_BOOTSTRAP_DIR/miniconda/bin/python" python3.12 python3.11 python3.10 python3)
  fi
  local candidate
  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 && python_version_ok "$candidate"; then
      command -v "$candidate"
      return
    fi
  done
  return 1
}

download_file() {
  local url="$1"
  local target="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fL "$url" -o "$target"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$target" "$url"
  else
    printf 'curl or wget is required to bootstrap Python automatically.\n' >&2
    return 1
  fi
}

glibc_version_text() {
  if command -v getconf >/dev/null 2>&1; then
    getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}' || true
  elif command -v ldd >/dev/null 2>&1; then
    ldd --version 2>/dev/null | head -n 1 | grep -Eo '[0-9]+\.[0-9]+' | head -n 1 || true
  fi
}

version_lt() {
  local left="$1"
  local right="$2"
  [[ "$(printf '%s\n%s\n' "$left" "$right" | sort -V | head -n 1)" != "$right" ]]
}

default_python_installer_url() {
  local arch="$1"
  local glibc_version
  glibc_version="$(glibc_version_text)"
  case "$arch" in
    x86_64|amd64)
      if [[ -n "$glibc_version" ]] && version_lt "$glibc_version" "2.28"; then
        # CentOS 7 ships glibc 2.17. New Miniconda installers require newer glibc.
        printf '%s\n' "https://repo.anaconda.com/miniconda/Miniconda3-py310_23.5.2-0-Linux-x86_64.sh"
      else
        printf '%s\n' "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
      fi
      ;;
    aarch64|arm64)
      printf '%s\n' "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
      ;;
    *)
      return 1
      ;;
  esac
}

bootstrap_python() {
  if [[ "${AUTO_INSTALL_PYTHON:-1}" != "1" ]]; then
    return 1
  fi
  local os arch installer_url installer_path install_dir
  os="$(uname -s)"
  arch="$(uname -m)"
  if [[ "$os" != "Linux" ]]; then
    printf 'Automatic Python bootstrap only supports Linux. Please install Python 3.10+ manually.\n' >&2
    return 1
  fi
  case "$arch" in
    x86_64|amd64|aarch64|arm64)
      installer_url="${PYTHON_INSTALLER_URL:-$(default_python_installer_url "$arch")}"
      ;;
    *)
      printf 'Unsupported CPU architecture for automatic Python bootstrap: %s\n' "$arch" >&2
      return 1
      ;;
  esac

  mkdir -p "$PYTHON_BOOTSTRAP_DIR"
  install_dir="$PYTHON_BOOTSTRAP_DIR/miniconda"
  installer_path="$PYTHON_BOOTSTRAP_DIR/miniconda-installer.sh"
  if [[ -x "$install_dir/bin/python" ]] && python_version_ok "$install_dir/bin/python"; then
    info "private Python runtime already available: $install_dir/bin/python"
    return 0
  fi

  info "no suitable Python found; installing private Python runtime"
  info "Python runtime directory: $install_dir"
  info "download: $installer_url"
  rm -rf "$install_dir"
  download_file "$installer_url" "$installer_path"
  bash "$installer_path" -b -p "$install_dir"
  rm -f "$installer_path"

  if ! python_version_ok "$install_dir/bin/python"; then
    printf 'Bootstrapped Python is still older than 3.10: %s\n' "$(python_version_text "$install_dir/bin/python")" >&2
    return 1
  fi
  info "installed private Python $("$install_dir/bin/python" -V 2>&1)"
}

stop_existing() {
  local stopped=0
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if is_running "$pid"; then
      info "stopping existing web runner pid=$pid"
      kill "$pid" >/dev/null 2>&1 || true
      for _ in {1..30}; do
        if ! is_running "$pid"; then
          break
        fi
        sleep 0.2
      done
      if is_running "$pid"; then
        info "forcing stop for pid=$pid"
        kill -9 "$pid" >/dev/null 2>&1 || true
      fi
      stopped=1
    fi
    rm -f "$PID_FILE"
  fi

  # Clean up older instances started without the pid file.
  local extra_pids
  extra_pids="$(pgrep -f "uvicorn ${APP_MODULE}" 2>/dev/null || true)"
  if [[ -n "$extra_pids" ]]; then
    while IFS= read -r pid; do
      [[ -z "$pid" || "$pid" == "$$" ]] && continue
      info "stopping orphan web runner pid=$pid"
      kill "$pid" >/dev/null 2>&1 || true
      stopped=1
    done <<< "$extra_pids"
  fi

  if [[ "$stopped" == "1" ]]; then
    sleep 0.5
  fi
}

ensure_python() {
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    if python_version_ok "$VENV_DIR/bin/python"; then
      return
    fi
    info "existing virtual environment uses Python $(python_version_text "$VENV_DIR/bin/python"), but Python 3.10+ is required"
    rm -rf "$VENV_DIR"
  fi
  local python_bin
  if ! python_bin="$(resolve_python)"; then
    if bootstrap_python; then
      python_bin="$(resolve_python)"
    else
      printf 'Python 3.10 or newer is required.\n' >&2
      printf 'Install python3.10/python3.11 manually, or run with a custom interpreter: PYTHON=/path/to/python3.10 ./start_web.sh\n' >&2
      printf 'For offline servers, set PYTHON_INSTALLER_URL to an internal Miniconda installer URL.\n' >&2
      exit 1
    fi
  fi
  info "using Python $("$python_bin" -V 2>&1)"
  info "creating virtual environment: $VENV_DIR"
  "$python_bin" -m venv "$VENV_DIR"
}

deps_ok() {
  "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import fastapi
import uvicorn
import jinja2
import multipart
PY
}

install_deps_if_needed() {
  ensure_python
  if deps_ok; then
    info "dependencies already available"
    return
  fi
  info "installing web dependencies"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r requirements-web.txt
}

ensure_port_available() {
  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi
  local listeners
  listeners="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$listeners" ]]; then
    return
  fi
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    local cmd
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$cmd" == *"uvicorn ${APP_MODULE}"* ]]; then
      info "stopping existing listener on port $PORT pid=$pid"
      kill "$pid" >/dev/null 2>&1 || true
      sleep 0.5
    else
      printf 'Port %s is already used by pid=%s: %s\n' "$PORT" "$pid" "$cmd" >&2
      printf 'Set another port, for example: PORT=8001 ./start_web.sh\n' >&2
      exit 1
    fi
  done <<< "$listeners"
}

start_server() {
  : > "$LOG_FILE"
  info "starting web runner on http://${HOST}:${PORT}"
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup "$VENV_DIR/bin/python" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
  else
    nohup "$VENV_DIR/bin/python" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
  fi
  local pid="$!"
  disown "$pid" >/dev/null 2>&1 || true
  echo "$pid" > "$PID_FILE"

  for _ in {1..30}; do
    if is_running "$pid" && grep -q "Uvicorn running" "$LOG_FILE" 2>/dev/null; then
      info "started pid=$pid"
      info "log: $LOG_FILE"
      info "stop/restart by running this script again"
      return
    fi
    if ! is_running "$pid"; then
      printf 'Web runner failed to start. Log:\n' >&2
      tail -80 "$LOG_FILE" >&2 || true
      rm -f "$PID_FILE"
      exit 1
    fi
    sleep 0.3
  done

  info "started pid=$pid"
  info "log: $LOG_FILE"
  info "server is still warming up; check the log if the page is not reachable"
}

stop_existing
install_deps_if_needed
ensure_port_available
start_server

#!/usr/bin/env bash
set -euo pipefail

# Project root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Ensure venv
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
pip -q install -U pip >/dev/null
pip -q install -r requirements.txt

export PYTHONPATH="$ROOT_DIR"
PORT="${APP_PORT:-8002}"

exec uvicorn src.backend.app.main:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --reload

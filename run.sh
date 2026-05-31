#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "Missing virtualenv at $VENV" >&2
  echo "Create it with: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5050}"

export HOST PORT
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV/bin/python" -m background_remover

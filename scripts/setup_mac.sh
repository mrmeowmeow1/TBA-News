#!/usr/bin/env bash
# TBA standard macOS setup (Flask + NLP + Swara/Madhur). No optional Piper/Parler.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! command -v python3.11 >/dev/null 2>&1; then
  echo "Python 3.11 not found. Install it first: brew install python@3.11" >&2
  exit 1
fi
echo "[1/4] Creating Python 3.11 virtual environment..."
python3.11 -m venv .venv311
PYTHON="$ROOT/.venv311/bin/python"
echo "[2/4] Updating pip in the virtual environment..."
"$PYTHON" -m pip install --upgrade pip
echo "[3/4] Installing the main app, ML and online narrator dependencies..."
"$PYTHON" -m pip install -r requirements.txt
echo "[4/4] Preparing local config..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo 'Created .env from .env.example (review PORT and optional settings).'
else
  echo 'Existing .env left unchanged.'
fi
echo ''
echo 'Setup complete. Start TBA with:'
echo '  source .venv311/bin/activate'
echo '  python app.py'
echo 'Then open http://127.0.0.1:5000 (or your configured PORT).'
echo 'Optional Piper / Divya were NOT installed.'

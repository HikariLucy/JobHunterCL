#!/usr/bin/env bash
# Inicia JobHunter CL (FastAPI + React) en 127.0.0.1. Ctrl+C para cerrar.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "[1/3] Creando entorno virtual..."
  python3 -m venv .venv || { echo "Instala python3-venv: sudo apt install python3-venv"; exit 1; }
fi

.venv/bin/python -c "import sys; assert sys.version_info >= (3, 11)" \
  || { echo "[ERROR] Se requiere Python 3.11+"; exit 1; }

if ! .venv/bin/python -c "import fastapi, uvicorn, requests, bs4" >/dev/null 2>&1; then
  echo "[2/3] Instalando dependencias de Python..."
  .venv/bin/python -m pip install -r requirements.txt
fi

echo "[3/3] Iniciando JobHunter CL..."
exec .venv/bin/python start.py "$@"

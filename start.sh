#!/usr/bin/env bash
# Sobe a loja completa (seed + servidor) em http://127.0.0.1:8099
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q fastapi "uvicorn[standard]" sqlalchemy jinja2 python-jose bcrypt python-multipart requests
fi
if [ ! -f data/catalog.json ]; then
  echo "[!] data/catalog.json nao existe. Rode: .venv/bin/python scraper/scrape_catalog.py"
  exit 1
fi
exec bash server/run.sh

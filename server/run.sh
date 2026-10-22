#!/usr/bin/env bash
# Sobe a loja: cria/atualiza o schema (e roda o seed se o banco estiver vazio),
# depois sobe o uvicorn em 127.0.0.1:8099.
#
# Funciona com SQLite local (default) ou com DATABASE_URL (Postgres/serverless).
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SERVER_DIR/.." && pwd)"
PORT="${PORT:-8099}"
HOST="${HOST:-127.0.0.1}"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PY="$ROOT_DIR/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

export PYTHONPATH="$SERVER_DIR:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export SECRET_KEY="${SECRET_KEY:-dev-secret-friboi-online-troque-em-producao}"
export DEV_MODE="${DEV_MODE:-1}"
export CATALOG_PATH="${CATALOG_PATH:-$ROOT_DIR/data/catalog.json}"

if [ -z "${DATABASE_URL:-}" ]; then
  mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/data/images/products"
  if [ ! -f "$CATALOG_PATH" ]; then
    echo "==> AVISO: catálogo ausente ($CATALOG_PATH). Subindo com banco vazio (rode o scraper T1 e o seed)."
  fi
else
  echo "==> Usando DATABASE_URL ($(printf '%s' "$DATABASE_URL" | sed 's#://.*@#://***@#'))"
fi

cd "$SERVER_DIR"
echo "==> Schema + seed idempotente"
"$PY" - <<'PYEOF'
import sys
sys.path.insert(0, ".")
from db import DB_PATH, DATABASE_URL, init_db
init_db()  # cria as tabelas e roda o seed se products estiver vazio
print(f"==> Banco pronto: {DATABASE_URL or DB_PATH}")
PYEOF

echo "==> Friboi Online em http://$HOST:$PORT"
exec "$PY" -m uvicorn app:app --host "$HOST" --port "$PORT"

#!/usr/bin/env bash
# Sobe uma instância ISOLADA da loja na porta 8199, roda a suíte E2E e derruba.
# Uso: bash tests/run_e2e.sh [suíte...]   (default: api pages)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8199}"
BASE="http://127.0.0.1:$PORT"
ARTI="$ROOT/tests/artifacts"
mkdir -p "$ARTI"
LOG="$ARTI/server_${PORT}.log"

cd "$ROOT"

# Banco de teste: cópia consistente do SQLite real (não poluir data/store.db).
mkdir -p "$ROOT/tests/tmp"
export DB_PATH="$ROOT/tests/tmp/store_test.db"
"$ROOT/.venv/bin/python" - "$ROOT/data/store.db" "$DB_PATH" <<'PYCOPY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
print(f"==> banco de teste: copia de data/store.db -> {sys.argv[2]}")
PYCOPY
STORE_MTIME_ANTES="$(date -r "$ROOT/data/store.db" +%s)"
: > "$LOG"
PORT="$PORT" setsid bash server/run.sh >> "$LOG" 2>&1 &
SRV_PID=$!
trap 'kill -TERM -"$SRV_PID" 2>/dev/null || kill "$SRV_PID" 2>/dev/null' EXIT

echo "==> subindo servidor em $BASE (pid $SRV_PID), log em tests/artifacts/server_${PORT}.log"
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$BASE/api/health" 2>/dev/null)"
  if [ "$code" = "200" ]; then echo "==> pronto em ${i}s"; break; fi
  sleep 1
done
if [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$BASE/api/health")" != "200" ]; then
  echo "!! servidor não subiu"; tail -40 "$LOG"; exit 1
fi
echo "==> health: $(curl -s "$BASE/api/health")"
echo

rc=0
for suite in "${@:-api pages}"; do
  for s in $suite; do
    case "$s" in
      api)   "$ROOT/.venv/bin/python" "$ROOT/tests/e2e_api.py" "$BASE" || rc=1 ;;
      pages) "$ROOT/.venv/bin/python" "$ROOT/tests/pages_assets.py" "$BASE" || rc=1 ;;
      vis)   python3 "$ROOT/tests/visual_check.py" "$BASE" || rc=1 ;;
      vercel) python3 "$ROOT/tests/vercel_check.py" || rc=1 ;;
    esac
  done
done

echo
# prova de que o banco real não foi tocado
STORE_MTIME_DEPOIS="$(date -r "$ROOT/data/store.db" +%s)"
if [ "$STORE_MTIME_ANTES" = "$STORE_MTIME_DEPOIS" ]; then
  echo "==> data/store.db do projeto NÃO foi modificado (mtime $STORE_MTIME_DEPOIS)"
else
  echo "!! data/store.db MUDOU durante os testes ($STORE_MTIME_ANTES -> $STORE_MTIME_DEPOIS)"
fi
echo
echo "==> log do servidor (últimas 25 linhas)"
tail -25 "$LOG"
exit $rc

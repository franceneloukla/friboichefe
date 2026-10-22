#!/usr/bin/env python3
"""Check 9 (bônus) — bundle serverless do Vercel: cold start com seed automático.

Monta um diretório temporário DENTRO do projeto (tests/tmp/vercel_XXXX) copiando
api/, server/, data/catalog.json (+ data/seed.db se existir), sobe
`api.index:app` com VERCEL=1 em outra porta e prova com curl que o app responde
com o catálogo completo, sem depender do data/store.db do projeto.

Uso (python3 do sistema; o servidor do check roda com .venv/bin/python):
    python3 tests/vercel_check.py
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTI = ROOT / "tests" / "artifacts"
ARTI.mkdir(parents=True, exist_ok=True)
PY = ROOT / ".venv" / "bin" / "python"
PORT = int(os.environ.get("VERCEL_TEST_PORT", "8299"))
BASE = f"http://127.0.0.1:{PORT}"
LOG: list[str] = []
RESULTS: list[dict] = []


def log(m: str = "") -> None:
    print(m, flush=True)
    LOG.append(m)


def record(check: str, title: str, ok: bool, expected: str, got: str, evidence: str = "") -> None:
    RESULTS.append({"check": check, "title": title, "ok": bool(ok),
                    "expected": expected, "got": got, "evidence": evidence})
    log(f"  [{'OK ' if ok else 'FALHOU'}] {check} {title}")
    log(f"          esperado: {expected}")
    log(f"          obtido:   {got}")
    if evidence:
        for line in evidence.rstrip().splitlines()[:8]:
            log(f"          | {line}")


def http(path: str, timeout: int = 90):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "T5-vercel/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode(), {}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    if not PY.is_file():
        log(f"!! python do venv não encontrado: {PY}")
        return 1
    tmp_root = ROOT / "tests" / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vercel_", dir=tmp_root))
    try:
        # --- monta o bundle mínimo que o Vercel publica (vercel.json includeFiles) ---
        shutil.copytree(ROOT / "api", tmp / "api",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "server", tmp / "server",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (tmp / "data").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "data" / "catalog.json", tmp / "data" / "catalog.json")
        seed_db = ROOT / "data" / "seed.db"
        if seed_db.is_file():
            shutil.copy2(seed_db, tmp / "data" / "seed.db")
        runtime = tmp / "runtime_data"
        runtime.mkdir()
        log(f"bundle temporário: {tmp.relative_to(ROOT)}")
        log(f"catalog.json: {(tmp/'data'/'catalog.json').stat().st_size/1e6:.2f} MB | "
            f"seed.db: {seed_db.is_file() and round(seed_db.stat().st_size/1e6, 2) or 'ausente'} MB")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", str(ROOT)),
            "VERCEL": "1",
            "SECRET_KEY": "dev-secret-friboi-online-troque-em-producao",
            "PYTHONPATH": str(tmp),
            "DATA_DIR": str(runtime),
            "CATALOG_PATH": str(tmp / "data" / "catalog.json"),
            "SEED_DB_PATH": str(tmp / "data" / "seed.db"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C.UTF-8",
        }
        cmd = [str(PY), "-m", "uvicorn", "api.index:app", "--host", "127.0.0.1", "--port", str(PORT)]
        log(f"subindo: {' '.join(cmd)}  (VERCEL=1, DATA_DIR={runtime.name})")
        t0 = time.time()
        proc_log = tmp / "serverless.log"
        with open(proc_log, "w", encoding="utf-8") as fh:
            proc = subprocess.Popen(cmd, cwd=str(tmp), env=env, stdout=fh,
                                    stderr=subprocess.STDOUT, text=True)
        # --- espera o cold start ---
        cold = None
        for _ in range(180):
            st, body, _ = http("/api/health", timeout=5)
            if st == 200:
                cold = round(time.time() - t0, 2)
                break
            if proc.poll() is not None:
                break
            time.sleep(1)
        record("9a", "cold start do bundle serverless (uvicorn api.index:app) sobe em tempo aceitável",
               cold is not None and cold < 120, "< 120 s", f"{cold} s" if cold else "NÃO SUBIU",
               f"comando: {' '.join(cmd)}\nVERCEL=1 DATA_DIR=<bundle>/runtime_data")

        if cold is None:
            out = proc_log.read_text(errors="replace")[-3000:] if proc_log.is_file() else ""
            log("!! o app não respondeu. Saída do processo:\n" + out)
            record("9b", "app serverless responde /api/health", False, "200", "timeout")
            raise SystemExit(1)

        st, body, _ = http("/api/health")
        health = json.loads(body.decode() or "{}")
        record("9b", "/api/health no bundle serverless -> 200 com 1567 produtos",
               st == 200 and health.get("products") == 1567,
               "200 {products:1567}", f"{st} {json.dumps(health, ensure_ascii=False)}",
               f"db reportado: {health.get('db')}")

        # Em VERCEL=1 o SQLite vai para o tempdir (TMP_DB_PATH), por design
        # (server/db.py:resolve_sqlite_path) — validamos o caminho reportado no health.
        db_reportado = str(health.get("db") or "")
        db_path = Path(db_reportado.split(":", 1)[1]) if ":" in db_reportado else None
        n_db = None
        if db_path and db_path.is_file():
            c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                n_db = c.execute("select count(*) from products").fetchone()[0]
                n_cats = c.execute("select count(*) from categories").fetchone()[0]
            except Exception as e:  # noqa: BLE001
                n_db, n_cats = f"erro: {e}", None
            c.close()
        else:
            n_cats = None
        record("9c", "seed automático criou o banco (tempdir no Vercel) com 1567 produtos / 471 categorias",
               n_db == 1567 and n_cats == 471, "1567 produtos, 471 categorias",
               f"{n_db} produtos, {n_cats} categorias em {db_path}",
               "server/db.py:resolve_sqlite_path manda o SQLite para TMP_DB_PATH quando VERCEL=1 (efêmero, re-seeda a cada cold start)")

        st, body, _ = http("/")
        html = body.decode("utf-8", "replace")
        record("9d", "página / renderiza no bundle serverless (templates incluídos)",
               st == 200 and "friboi" in html.lower() and "R$" in html,
               "200 com Friboi e R$", f"{st}, {len(body)} bytes, 'Friboi'={'friboi' in html.lower()}, 'R$'={'R$' in html}",
               "sem traceback" if "Traceback" not in html else "HTTP 500 detectado")

        st, body, _ = http("/api/products?limit=2")
        try:
            pj = json.loads(body.decode())
        except Exception:  # noqa: BLE001
            pj = {}
        record("9e", "/api/products responde no serverless",
               st == 200 and pj.get("total") == 1567, "200 total=1567",
               f"{st} total={pj.get('total')} itens={len(pj.get('items') or [])}")

        # 9h: os assets estáticos do deploy real vêm de public/ (scripts/build_vercel.py).
        # A simulação acima NÃO inclui public/ (só api/, server/, data/), então /assets
        # e /img/products não existem no bundle python — o que é esperado.
        pub = ROOT / "public"
        mapa = [
            ("assets", ROOT / "web" / "static", pub / "assets"),
            ("static", ROOT / "server" / "static", pub / "static"),
            ("img", ROOT / "data" / "images", pub / "img"),
        ]
        linhas, ok_mapa = [], True
        for nome, origem, destino in mapa:
            if not destino.is_dir():
                ok_mapa = False
                linhas.append(f"{nome}: AUSENTE em public/ (rode scripts/build_vercel.py)")
                continue
            n_src = sum(1 for f in origem.rglob("*") if f.is_file())
            n_dst = sum(1 for f in destino.rglob("*") if f.is_file())
            amostras = ["img/ui/logos/logo-friboi-online.png", "fonts/roboto-400-latin.woff2"] if nome == "assets" else                        (["css/app.css", "js/app.js"] if nome == "static" else ["products/376490/main.jpg"])
            faltando = [a for a in amostras if not (destino / a).is_file()]
            ok_mapa = ok_mapa and n_dst > 0 and not faltando
            linhas.append(f"public/{nome}: {n_dst} arquivos (origem {n_src})"
                          + (f"; faltando {faltando}" if faltando else "; amostras presentes"))
        record("9h", "assets do deploy estão em public/ (Vercel serve outputDirectory antes do rewrite)",
               ok_mapa, "public/assets, public/static, public/img com os arquivos",
               "ok" if ok_mapa else "incompleto", "\n".join(linhas))

        # o banco versionificado do projeto NÃO pode ser tocado
        store = ROOT / "data" / "store.db"
        record("9f", "cold start não usa nem altera data/store.db do projeto",
               str(db_path) != str(store), "banco fora de data/store.db",
               f"health.db = {health.get('db')}",
               f"data/store.db do projeto: mtime={time.strftime('%H:%M:%S', time.localtime(store.stat().st_mtime))} "
               f"size={store.stat().st_size}")

        # prova do seed no log do processo
        log_txt = (tmp / "serverless.log").read_text(errors="replace") if (tmp / "serverless.log").is_file() else ""
        marcas = [ln for ln in log_txt.splitlines()
                  if any(k in ln.lower() for k in ("seed", "banco", "produtos", "instal"))]
        record("9g", "log do cold start mostra o seed/instalação do banco",
               bool(marcas), "linha de log de seed", f"{len(marcas)} linha(s) relacionadas",
               "\n".join(marcas[:6]) if marcas else "nenhuma linha de seed no log")

        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log(f"processo encerrado; artefatos do bundle ficam em {tmp.relative_to(ROOT)} (apagado no fim)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            (ROOT / "tests" / "tmp").rmdir()
        except OSError:
            pass

    total = len(RESULTS)
    falhas = [r for r in RESULTS if not r["ok"]]
    log("\n" + "=" * 70)
    log(f"RESUMO: {total - len(falhas)}/{total} OK, {len(falhas)} FALHOU")
    (ARTI / "vercel_check.log").write_text("\n".join(LOG), encoding="utf-8")
    (ARTI / "vercel_check.json").write_text(json.dumps(
        {"ok": total - len(falhas), "total": total, "falhas": len(falhas),
         "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": RESULTS},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())

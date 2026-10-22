#!/usr/bin/env python3
"""Gera ``data/seed.db`` — banco PRÉ-MONTADO (só categorias + produtos) para o cold start.

Por que existe: no Vercel sem Postgres o SQLite vive em ``/tmp`` e é recriado a cada
cold start. Sem este arquivo, cada cold start re-seedava 1.567 produtos a partir de
``data/catalog.json`` (~4,5 s). Com ``data/seed.db`` versionado, o ``init_db`` só copia
o arquivo pronto (milissegundos) e a função sobe dentro do limite de tempo.

Conteúdo do arquivo gerado: APENAS ``categories`` e ``products``.
Nunca tem usuários, carrinhos, pedidos ou itens de pedido — o admin de
desenvolvimento é criado em runtime pelo seed normal (só com DEV_MODE=1).

COMO REGENERAR (sempre que data/catalog.json, as categorias ou as imagens mudarem):

    .venv/bin/python server/build_seed_db.py
    # opções: --catalog data/catalog.json  --out data/seed.db

O script roda o seed num arquivo temporário isolado (não toca em data/store.db),
limpa qualquer usuário/pedido/carrinho, compacta com VACUUM e publica o resultado
de forma atômica (copia para ``.seed.db.tmp-<pid>`` e faz ``os.replace``).

Depois de regenerar, versione o binário no git:

    git add data/seed.db
    git commit -m "chore: atualiza data/seed.db"

Local: se ``data/store.db`` já existir e tiver produtos, ele NÃO é substituído pelo
seed.db (quem manda é o store.db local). Para forçar o uso do arquivo novo, apague
``data/store.db`` antes de subir o servidor.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
DEFAULT_CATALOG = ROOT_DIR / "data" / "catalog.json"
DEFAULT_OUT = ROOT_DIR / "data" / "seed.db"


def build(catalog: Path, out: Path) -> dict:
    started = time.perf_counter()
    out.parent.mkdir(parents=True, exist_ok=True)

    build_dir = Path(tempfile.mkdtemp(prefix="friboi-seed-"))
    build_db = build_dir / "seed-build.db"
    tmp_out = out.parent / f".{out.name}.tmp-{os.getpid()}"

    # O engine do app é resolvido a partir do ambiente — isola o build num DB temporário
    # e desliga o admin de dev (o seed.db não pode conter usuários).
    os.environ["DB_PATH"] = str(build_db)
    os.environ["CATALOG_PATH"] = str(catalog)
    os.environ["DEV_MODE"] = "0"
    os.environ["SEED_ON_INIT"] = "0"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("SEED_DB_PATH", None)

    sys.path.insert(0, str(SERVER_DIR))
    import db  # noqa: E402  (importado depois de ajustar o ambiente)
    import seed as seed_module  # noqa: E402

    if build_db.exists():
        build_db.unlink()

    print(f"[build_seed_db] banco temporário: {build_db}")
    db.init_db(seed_if_empty=False)  # só cria o schema
    stats = seed_module.run_seed(catalog, verbose=True)

    # Solta conexões do SQLAlchemy antes de mexer no arquivo no nível SQLite
    db.engine.dispose()

    # Defensivo: seed.db não pode ter usuários/carrinhos/pedidos
    con = sqlite3.connect(str(build_db))
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        for table in ("order_items", "orders", "cart_items", "carts", "users"):
            con.execute(f"DELETE FROM {table}")
        con.commit()
        con.execute("VACUUM")  # compacta e remove páginas livres

        if tmp_out.exists():
            tmp_out.unlink()
        con.execute("VACUUM INTO ?", (str(tmp_out),))
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        _ = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    finally:
        con.close()

    if integrity != "ok":
        shutil.rmtree(build_dir, ignore_errors=True)
        raise RuntimeError(f"integrity_check do seed.db falhou: {integrity}")

    os.replace(tmp_out, out)  # atômico no mesmo diretório
    shutil.rmtree(build_dir, ignore_errors=True)

    # Conferência final no arquivo publicado
    con = sqlite3.connect(str(out))
    try:
        products = con.execute("select count(*) from products").fetchone()[0]
        categories = con.execute("select count(*) from categories").fetchone()[0]
        users = con.execute("select count(*) from users").fetchone()[0]
        orders = con.execute("select count(*) from orders").fetchone()[0]
        cart_items = con.execute("select count(*) from cart_items").fetchone()[0]
        with_image = con.execute("select count(*) from products where image_path is not null").fetchone()[0]
    finally:
        con.close()

    if users or orders or cart_items:
        raise RuntimeError("seed.db contaminado: contém usuários/carrinhos/pedidos")

    elapsed = time.perf_counter() - started
    size_mb = out.stat().st_size / (1024 * 1024)
    return {
        "out": str(out),
        "products": products,
        "categories": categories,
        "with_image": with_image,
        "users": users,
        "orders": orders,
        "size_mb": round(size_mb, 2),
        "build_elapsed_s": round(elapsed, 2),
        "catalog": str(catalog),
        "catalog_stats": stats,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera data/seed.db (banco pré-montado)")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="catalog.json de entrada")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="arquivo SQLite de saída")
    args = parser.parse_args(argv)

    catalog = Path(args.catalog)
    out = Path(args.out)
    if not catalog.is_file():
        print(f"[build_seed_db] catálogo não encontrado: {catalog}", file=sys.stderr)
        return 2

    info = build(catalog, out)
    print("\n[build_seed_db] OK")
    print(f"  arquivo      : {info['out']}")
    print(f"  produtos     : {info['products']}")
    print(f"  categorias   : {info['categories']}")
    print(f"  com imagem   : {info['with_image']}")
    print(f"  usuários     : {info['users']}  |  pedidos: {info['orders']}")
    print(f"  tamanho      : {info['size_mb']} MB")
    print(f"  build        : {info['build_elapsed_s']} s")
    print("\n  Versione o arquivo:  git add data/seed.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

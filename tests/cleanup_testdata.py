#!/usr/bin/env python3
"""Remove os dados criados pelas rodadas E2E do T5 no banco real (data/store.db).

As rodadas iniciais (antes do isolamento em tests/tmp/store_test.db) criaram
usuários `t5.*@teste.local`, pedidos e carrinhos de visitante no banco de
produção local. Este script limpa **apenas** esses resíduos: nunca toca em
products/categories nem em usuários que não sejam de teste.

Uso:
    ./.venv/bin/python tests/cleanup_testdata.py            # simulação (dry-run)
    ./.venv/bin/python tests/cleanup_testdata.py --apply    # executa e faz VACUUM
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--apply" else ROOT / "data" / "store.db"
DB = Path(sys.argv[sys.argv.index("--db") + 1]) if "--db" in sys.argv else DB
APPLY = "--apply" in sys.argv

COND_USERS = "lower(email) LIKE 't5.%@teste.local' OR name IN ('Verificador T5','Segundo Usuário','Intruso','Páginas T5','Duplicado')"


def main() -> int:
    if not DB.is_file():
        print(f"banco não encontrado: {DB}")
        return 1
    c = sqlite3.connect(DB)
    c.execute("PRAGMA foreign_keys=ON")

    ids = [r[0] for r in c.execute(f"SELECT id FROM users WHERE {COND_USERS}")]
    q = lambda sql, *a: c.execute(sql, a).fetchone()[0]  # noqa: E731
    print(f"banco: {DB.name}")
    print(f"usuários de teste: {len(ids)} -> {ids}")
    n_orders = q(f"SELECT count(*) FROM orders WHERE user_id IN ({','.join(map(str, ids)) or 0})")
    n_items = q("SELECT count(*) FROM order_items WHERE order_id IN "
                f"(SELECT id FROM orders WHERE user_id IN ({','.join(map(str, ids)) or 0}))")
    n_carts = q(f"SELECT count(*) FROM carts WHERE user_id IN ({','.join(map(str, ids)) or 0})")
    n_citems = q("SELECT count(*) FROM cart_items WHERE cart_id IN "
                 f"(SELECT id FROM carts WHERE user_id IN ({','.join(map(str, ids)) or 0}))")
    n_vazios = q("SELECT count(*) FROM carts c WHERE c.user_id IS NULL "
                 "AND NOT EXISTS (SELECT 1 FROM cart_items ci WHERE ci.cart_id = c.id)")
    print(f"pedidos: {n_orders} | order_items: {n_items} | carrinhos de teste: {n_carts} "
          f"({n_citems} itens) | carrinhos de visitante vazios: {n_vazios}")
    print(f"produtos/ categorias (intocados): "
          f"{q('SELECT count(*) FROM products')} / {q('SELECT count(*) FROM categories')}")

    if not APPLY:
        print("\n[dry-run] nada foi alterado. Rode com --apply para limpar.")
        return 0

    with c:
        c.execute("DELETE FROM order_items WHERE order_id IN "
                  f"(SELECT id FROM orders WHERE user_id IN ({','.join(map(str, ids)) or 0}))")
        c.execute(f"DELETE FROM orders WHERE user_id IN ({','.join(map(str, ids)) or 0})")
        c.execute("DELETE FROM cart_items WHERE cart_id IN "
                  f"(SELECT id FROM carts WHERE user_id IN ({','.join(map(str, ids)) or 0}))")
        c.execute(f"DELETE FROM carts WHERE user_id IN ({','.join(map(str, ids)) or 0})")
        c.execute("DELETE FROM carts WHERE user_id IS NULL "
                  "AND NOT EXISTS (SELECT 1 FROM cart_items ci WHERE ci.cart_id = carts.id)")
        c.execute(f"DELETE FROM users WHERE id IN ({','.join(map(str, ids)) or 0})")
    c.execute("VACUUM")
    print("\n[apply] resíduos removidos. Estado agora:")
    for t in ("users", "carts", "cart_items", "orders", "order_items", "products", "categories"):
        print(f"  {t}: {q(f'SELECT count(*) FROM {t}')}")
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

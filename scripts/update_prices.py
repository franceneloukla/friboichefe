#!/usr/bin/env python3
"""Atualiza preços do catálogo a partir de um CSV.

O catálogo extraído do site original vem com o "preço de tabela" do próprio
site (R$ 9.999,00 em todos os itens) porque a loja não expõe o preço de venda
na API pública. Este script é o caminho para colocar os SEUS preços: edite
`data/prices.csv` (colunas sku,name,category,price) e rode

    .venv/bin/python scripts/update_prices.py                 # aplica
    .venv/bin/python scripts/update_prices.py --export        # (re)gera o CSV
    .venv/bin/python scripts/update_prices.py --csv outro.csv # outro arquivo

O script grava no banco configurado pelo app (data/store.db local, ou
DATABASE_URL se definido) — usa o mesmo db.py do servidor, sem duplicar lógica.
"""
from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import db as appdb  # noqa: E402
from server.models import Product  # noqa: E402
from sqlalchemy import select  # noqa: E402

CSV_PATH = ROOT / "data" / "prices.csv"


def export(csv_path: Path) -> int:
    appdb.init_db(seed_if_empty=True)
    with appdb.SessionLocal() as s:
        rows = s.execute(select(Product).order_by(Product.name)).scalars().all()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["sku", "name", "category", "price", "sale_price"])
            for p in rows:
                w.writerow([
                    p.sku or p.id,
                    p.name,
                    p.category_id or "",
                    f"{p.price:.2f}" if p.price is not None else "",
                    f"{p.sale_price:.2f}" if p.sale_price is not None else "",
                ])
    print(f"Exportado {len(rows)} produtos para {csv_path.relative_to(ROOT)}")
    return len(rows)


def parse_money(raw: str) -> Decimal | None:
    txt = (raw or "").strip().replace("R$", "").replace(" ", "")
    if not txt:
        return None
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return Decimal(txt)
    except InvalidOperation:
        return None


def apply(csv_path: Path) -> int:
    appdb.init_db(seed_if_empty=True)
    updated = skipped = 0
    with appdb.SessionLocal() as s:
        by_sku = {p.sku: p for p in s.execute(select(Product)).scalars().all() if p.sku}
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            for line in csv.DictReader(fh):
                sku = (line.get("sku") or "").strip()
                prod = by_sku.get(sku)
                if not prod:
                    skipped += 1
                    continue
                price = parse_money(line.get("price", ""))
                sale = parse_money(line.get("sale_price", ""))
                if price is not None:
                    prod.price = float(price)
                if sale is not None:
                    prod.sale_price = float(sale)
                updated += 1
        s.commit()
    print(f"Atualizados {updated} produtos ({skipped} SKUs não encontrados no banco).")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--export", action="store_true", help="gera o CSV a partir do banco")
    args = ap.parse_args()
    path = Path(args.csv)
    if args.export:
        export(path)
    else:
        if not path.is_file():
            print(f"[!] {path} não existe. Rode com --export para gerar o modelo.")
            return 1
        apply(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

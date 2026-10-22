#!/usr/bin/env python3
"""Seed do banco: importa ``data/catalog.json`` (T1) para o SQLite do app.

- Idempotente: faz upsert por ``id`` (rodar 2x não duplica nada).
- Categorias: cria a árvore (raiz -> ... -> folha), deriva o parent a partir de
  ``category_path``, calcula ``sort`` pela ordem da navegação e garante slug único.
- Produtos: recalcula ``image_path`` a partir do arquivo real em
  ``data/images/products/{id}/main.jpg``.
- Usuário admin de desenvolvimento só quando ``DEV_MODE=1``.

Uso:
    .venv/bin/python server/seed.py
    .venv/bin/python server/seed.py --catalog caminho/para/catalog.json
    CATALOG_PATH=/tmp/x.json .venv/bin/python server/seed.py --stats
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:  # pacote
    from .db import DATA_DIR, ROOT_DIR, SessionLocal, catalog_path, init_db
    from .models import Cart, CartItem, Category, Order, OrderItem, Product, User
    from .textutil import make_search_blob
    from . import auth
except ImportError:  # módulo solto (python server/seed.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from db import DATA_DIR, ROOT_DIR, SessionLocal, catalog_path, init_db  # type: ignore[no-redef]
    from models import (  # type: ignore[no-redef]
        Cart,
        CartItem,
        Category,
        Order,
        OrderItem,
        Product,
        User,
    )
    import auth  # type: ignore[no-redef]
    from textutil import make_search_blob  # type: ignore[no-redef]

IMAGES_DIR = DATA_DIR / "images"

# Ordem da navegação do site original (usada para o campo categories.sort)
NAV_ORDER = [
    "BOVINOS",
    "BOVINOS_IMPORTADOS",
    "AVES",
    "SUINOS",
    "PESCADOS",
    "BATATAS_E_VEGETAIS",
    "BATATAS",
    "CORDEIROS",
    "CHARQUES",
    "OUTROS",
]
# Categorias técnicas do Oracle Commerce Cloud que NUNCA devem virar nó do site
SKIP_CATEGORY_IDS = {"rootCategory", "nonNavigableCategory"}
PARENT_SENTINELS = {"rootcategory", "root", "nonnavigablecategory", "none", ""}

ROOT_LABELS = {
    "BOVINOS": "Bovinos",
    "BOVINOS_IMPORTADOS": "Bovinos Importados",
    "AVES": "Aves",
    "SUINOS": "Suínos",
    "PESCADOS": "Pescados",
    "BATATAS_E_VEGETAIS": "Batatas e Vegetais",
    "BATATAS": "Batatas e Vegetais",
    "CORDEIROS": "Cordeiros",
    "CHARQUES": "Charques",
    "OUTROS": "Outros",
}
ADMIN_EMAIL = os.environ.get("DEV_ADMIN_EMAIL", "admin@loja.local")
ADMIN_PASSWORD = os.environ.get("DEV_ADMIN_PASSWORD", "admin123")


def slugify(value: str) -> str:
    norm = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return slug or "item"


def to_decimal(value, default: Decimal | None = None) -> Decimal | None:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return default


def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def root_of(category_id: str | None) -> str:
    if not category_id:
        return "OUTROS"
    for root in NAV_ORDER:
        if category_id == root or category_id.startswith(root + "_"):
            return root
    return "OUTROS"


def root_rank(root: str) -> int:
    try:
        return NAV_ORDER.index(root)
    except ValueError:
        return len(NAV_ORDER)


def category_label(cat_id: str) -> str:
    if cat_id in ROOT_LABELS:
        return ROOT_LABELS[cat_id]
    return cat_id.replace("_", " ").title()


def derive_image_path(product_id: str, catalog_images: list | None) -> str | None:
    """Recalcula o caminho da imagem dentro de data/images, verificando o disco."""
    expected = f"products/{product_id}/main.jpg"
    if (IMAGES_DIR / expected).exists():
        return expected
    for image in catalog_images or []:
        if isinstance(image, dict):
            raw = image.get("file") or image.get("path") or ""
        else:
            raw = str(image or "")
        if not raw:
            continue
        raw = raw.split("?")[0].lstrip("/")
        if raw.startswith("data/images/"):
            raw = raw[len("data/images/"):]
        if raw.startswith("images/"):
            raw = raw[len("images/"):]
        if not raw.startswith("products/"):
            raw = f"products/{product_id}/{Path(raw).name}"
        if (IMAGES_DIR / raw).exists():
            return raw
        return raw  # caminho previsto (imagem pode ser baixada depois)
    return None


def build_categories(products: list[dict], catalog_categories: list[dict]) -> dict[str, dict]:
    """Monta {id: {id,name,slug,parent_id}} a partir do catálogo."""
    cats: dict[str, dict] = {}

    def put(cat_id: str, name: str | None = None, parent_id: str | None = None) -> None:
        if not cat_id or cat_id in SKIP_CATEGORY_IDS:
            return
        current = cats.get(cat_id)
        if current is None:
            cats[cat_id] = {
                "id": cat_id,
                "name": name or category_label(cat_id),
                "parent_id": parent_id,
            }
            return
        if name and (current["name"] == category_label(cat_id)):
            current["name"] = name
        if parent_id and not current["parent_id"]:
            current["parent_id"] = parent_id

    # 1) categorias declaradas no catalog.json
    for entry in catalog_categories or []:
        cat_id = str(entry.get("id") or entry.get("category_id") or "").strip()
        if not cat_id:
            continue
        name = entry.get("name") or entry.get("category_name")
        parent = entry.get("parent") or entry.get("parent_id")
        path = entry.get("path") or ""
        if not parent and path:
            parts = [p for p in str(path).split(">") if p and p.lower() != "rootcategory"]
            if len(parts) > 1:
                parent = parts[-2]
        if parent is not None and str(parent).lower() in PARENT_SENTINELS:
            parent = None
        put(cat_id, name, str(parent) if parent else None)

    # 2) categorias derivadas dos produtos (garante que nada fique órfão)
    for product in products:
        path = [str(p) for p in (product.get("category_path") or []) if p]
        leaf_id = product.get("category_id")
        if leaf_id and str(leaf_id) not in path:
            path.append(str(leaf_id))
        for index, cat_id in enumerate(path):
            parent = path[index - 1] if index > 0 else None
            if parent and parent.lower() in PARENT_SENTINELS:
                parent = None
            if cat_id.lower() in PARENT_SENTINELS:
                continue
            name = category_label(cat_id)
            if cat_id == str(leaf_id or "") and product.get("category_name"):
                name = product["category_name"]
            put(cat_id, name, parent)

    return cats


def assign_sort(cats: dict[str, dict]) -> dict[str, int]:
    """Ordena a árvore: raiz pela ordem da nav, depois alfabético; sort = posição*10."""
    children: dict[str | None, list[dict]] = {}
    for cat in cats.values():
        parent = cat["parent_id"] if cat["parent_id"] in cats else None
        cat["parent_id"] = parent
        children.setdefault(parent, []).append(cat)

    for key in children:
        children[key].sort(
            key=lambda c: (root_rank(root_of(c["id"])) if key is None else 0, c["name"].lower())
        )

    ordered: list[dict] = []

    def walk(parent: str | None) -> None:
        for cat in children.get(parent, []):
            ordered.append(cat)
            walk(cat["id"])

    walk(None)
    # categorias cujo parent sumiu/entrou em ciclo
    seen = {c["id"] for c in ordered}
    for cat in cats.values():
        if cat["id"] not in seen:
            ordered.append(cat)

    result: dict[str, int] = {}
    for index, cat in enumerate(ordered):
        result[cat["id"]] = index * 10
    return result


def upsert_categories(db, cats: dict[str, dict], order: dict[str, int]) -> int:
    existing = {c.id: c for c in db.query(Category).all()}
    used_slugs = {c.slug for c in existing.values()}
    count = 0
    for cat_id, data in cats.items():
        slug = slugify(data["name"])
        if slug in used_slugs and (cat_id not in existing or existing[cat_id].slug != slug):
            slug = f"{slug}-{slugify(cat_id)}"
        used_slugs.add(slug)
        row = existing.get(cat_id)
        if row is None:
            row = Category(id=cat_id, name=data["name"], slug=slug)
            db.add(row)
        else:
            row.name = data["name"]
            row.slug = slug
        row.parent_id = data["parent_id"]
        row.sort = order.get(cat_id, 0)
        count += 1
    return count


def upsert_products(db, products: list[dict]) -> tuple[int, int]:
    existing = {p.id: p for p in db.query(Product).all()}
    used_slugs = {p.slug for p in existing.values()}
    created = updated = 0
    for index, raw in enumerate(products, start=1):
        product_id = str(raw.get("id") or raw.get("sku") or "").strip()
        if not product_id:
            continue
        name = (raw.get("name") or "").strip() or f"Produto {product_id}"
        slug = (raw.get("slug") or "").strip().lower() or slugify(name)
        if not slug:
            slug = slugify(f"{name}-{product_id}")
        row = existing.get(product_id)
        if slug in used_slugs and (row is None or row.slug != slug):
            slug = f"{slug}-{product_id}"
        used_slugs.add(slug)

        price = to_decimal(raw.get("price"), Decimal("0.00")) or Decimal("0.00")
        sale_price = to_decimal(raw.get("sale_price"))
        if sale_price is not None and sale_price >= price:
            sale_price = None
        category_id = raw.get("category_id")
        category_id = str(category_id) if category_id else None
        stock = raw.get("stock") or "Indisponível"
        attrs = raw.get("attrs") or {}
        nutrition = raw.get("nutrition") or []

        values = dict(
            sku=str(raw.get("sku") or product_id),
            name=name,
            slug=slug,
            brand=raw.get("brand"),
            category_id=category_id,
            price=price,
            sale_price=sale_price,
            unit=(raw.get("unit") or "KG").upper()[:10],
            ean=raw.get("ean"),
            weight_min=to_decimal(raw.get("weight_min")),
            weight_avg=to_decimal(raw.get("weight_avg")),
            weight_max=to_decimal(raw.get("weight_max")),
            stock=stock,
            max_qty=max(1, to_int(raw.get("max_qty"), 1)),
            search_blob=make_search_blob(name, raw.get("brand"), raw.get("sku"), raw.get("ean")),
            description_html=raw.get("description_html"),
            video_url=raw.get("video_url"),
            image_path=derive_image_path(product_id, raw.get("images")),
            attrs_json=json.dumps(attrs, ensure_ascii=False) if attrs else None,
            nutrition_json=json.dumps(nutrition, ensure_ascii=False) if nutrition else None,
            active=True,
        )
        if row is None:
            db.add(Product(id=product_id, **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(row, key, value)
            updated += 1
        if index % 200 == 0:
            db.commit()
    db.commit()
    return created, updated


def ensure_admin(db) -> bool:
    """Cria o admin de desenvolvimento (só com DEV_MODE=1)."""
    if os.environ.get("DEV_MODE", "0") != "1":
        return False
    user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if user is None:
        db.add(
            User(
                name="Admin Friboi",
                email=ADMIN_EMAIL,
                password_hash=auth.hash_password(ADMIN_PASSWORD),
                is_admin=True,
            )
        )
        db.commit()
        return True
    user.is_admin = True
    db.commit()
    return False


def clear_data(db) -> None:
    """Zera catálogo e pedidos (mantém usuários). Usado com --reset."""
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(CartItem).delete()
    db.query(Cart).delete()
    db.query(Product).delete()
    db.query(Category).delete()
    db.commit()


def stats(db) -> dict:
    return {
        "categories": db.query(Category).count(),
        "products": db.query(Product).count(),
        "products_on_sale": db.query(Product).filter(Product.sale_price.is_not(None)).count(),
        "in_stock": db.query(Product).filter(Product.stock.ilike("dispon%")).count(),
        "with_image": db.query(Product).filter(Product.image_path.is_not(None)).count(),
        "users": db.query(User).count(),
        "orders": db.query(Order).count(),
    }


def run_seed(
    catalog_file: str | Path | None = None,
    *,
    reset: bool = False,
    verbose: bool = True,
) -> dict:
    """Importa o catálogo e devolve as estatísticas finais.

    Não cria o schema (quem chama deve ter rodado ``init_db``); é idempotente.
    Levanta ``FileNotFoundError`` se o catálogo não existir.
    """
    path = Path(catalog_file) if catalog_file else catalog_path()
    if not path.is_file():
        raise FileNotFoundError(str(path))

    def log(msg: str) -> None:
        if verbose:
            print(f"[seed] {msg}")

    log(f"lendo {path}")
    with path.open("r", encoding="utf-8") as fh:
        catalog = json.load(fh)
    products = catalog.get("products") or catalog.get("items") or []
    catalog_categories = catalog.get("categories") or []
    log(f"{len(products)} produtos, {len(catalog_categories)} categorias no JSON")

    db = SessionLocal()
    try:
        if reset:
            clear_data(db)
            log("dados anteriores removidos (--reset)")

        cats = build_categories(products, catalog_categories)
        order = assign_sort(cats)
        n_cats = upsert_categories(db, cats, order)
        db.commit()
        log(f"categorias: {n_cats}")

        created, updated = upsert_products(db, products)
        log(f"produtos: {created} criados, {updated} atualizados")

        admin_created = ensure_admin(db)
        if admin_created:
            log(f"admin de dev criado: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        elif os.environ.get("DEV_MODE", "0") != "1":
            log("DEV_MODE != 1 -> admin de dev não criado")

        result = stats(db)
        log("estatísticas:")
        log(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Importa data/catalog.json para o banco do app")
    parser.add_argument("--catalog", default=str(catalog_path()), help="caminho do catalog.json")
    parser.add_argument("--reset", action="store_true", help="apaga catálogo/pedidos antes de importar")
    parser.add_argument("--stats", action="store_true", help="apenas mostra estatísticas do banco")
    parser.add_argument("--quiet", action="store_true", help="silencia a saída detalhada")
    args = parser.parse_args(argv)

    # schema primeiro, mas sem auto-seed (o main controla o seed)
    init_db(seed_if_empty=False)

    if args.stats:
        db = SessionLocal()
        try:
            print(json.dumps(stats(db), indent=2, ensure_ascii=False))
        finally:
            db.close()
        return 0

    try:
        run_seed(args.catalog, reset=args.reset, verbose=not args.quiet)
    except FileNotFoundError:
        print(f"[seed] catálogo não encontrado: {args.catalog}", file=sys.stderr)
        print(
            "[seed] defina CATALOG_PATH ou rode o scraper (T1) para gerar data/catalog.json",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

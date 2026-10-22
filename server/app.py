"""Friboi Online — backend FastAPI (páginas Jinja2 + API JSON).

Implementa o CONTRATO (docs/CONTRATO.md):
- Mounts: /static -> server/static, /assets -> web/static, /img/products -> data/images/products
- Banco: SQLite em data/store.db via SQLAlchemy 2.0 (models.py)
- Auth: bcrypt + JWT HS256 em cookie httpOnly ``auth_token`` (e ``access_token`` no JSON)
- Carrinho: cookie ``cart_token`` (funciona anônimo e logado, funde no login)
- Pedidos: checkout 100% calculado no servidor a partir do preço do banco

Rodar: ``cd server && ./run.sh`` (uvicorn 127.0.0.1:8099).
"""

from __future__ import annotations

import logging
import math
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session

try:  # pacote (python -m server.app)
    from . import auth
    from .db import (
        DATA_DIR,
        DB_PATH,
        ROOT_DIR,
        SERVER_DIR,
        SessionLocal,
        backend_label,
        get_db,
        init_db,
    )
    from .models import (
        Cart,
        CartItem,
        Category,
        Order,
        OrderItem,
        Product,
        User,
        image_url,
        json_load,
        utcnow,
    )
except ImportError:  # módulo solto (uvicorn app:app rodando de dentro de server/)
    import auth  # type: ignore[no-redef]
    from db import (  # type: ignore[no-redef]
        DATA_DIR,
        DB_PATH,
        ROOT_DIR,
        SERVER_DIR,
        SessionLocal,
        backend_label,
        get_db,
        init_db,
    )
    from models import (  # type: ignore[no-redef]
        Cart,
        CartItem,
        Category,
        Order,
        OrderItem,
        Product,
        User,
        image_url,
        json_load,
        utcnow,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("friboi.backend")

STORE_NAME = "Friboi Online"
CART_COOKIE = "cart_token"
CART_COOKIE_MAX_AGE = 90 * 24 * 60 * 60

TEMPLATES_DIR = SERVER_DIR / "templates"
STATIC_DIR = SERVER_DIR / "static"
WEB_STATIC_DIR = ROOT_DIR / "web" / "static"
IMAGES_DIR = DATA_DIR / "images" / "products"

CENT = Decimal("0.01")


def money(value: Decimal | float | int | None) -> Decimal:
    """Converte qualquer número em Decimal com 2 casas (arredondamento comercial)."""
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def as_float(value: Decimal | float | int | None) -> float:
    return float(money(value))


# ---------------------------------------------------------------------------
# App, templates e mounts
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Garante o schema no boot (o seed é responsável pelos dados)."""
    init_db()  # cria schema, loga o backend e roda o seed se products estiver vazio
    if not TEMPLATES_DIR.exists():
        logger.warning("Diretório de templates ausente: %s (T4)", TEMPLATES_DIR)
    yield


app = FastAPI(
    title="Friboi Online",
    description="Loja própria: catálogo, autenticação, carrinho e pedidos.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["store_name"] = STORE_NAME
templates.env.globals["cart_cookie"] = CART_COOKIE


def _brl(value: Any) -> str:
    """Filtro Jinja: 129.9 -> 'R$ 129,90'."""
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


templates.env.filters["brl"] = _brl

def mount_if_dir(route: str, directory: Path, name: str) -> bool:
    """Monta um StaticFiles apenas se o diretório existir.

    Em serverless (Vercel) os arquivos são servidos por CDN a partir de public/,
    então o mount é opcional e nunca deve impedir o boot.
    """
    if directory.is_dir():
        app.mount(route, StaticFiles(directory=str(directory)), name=name)
        logger.info("Mount %s -> %s", route, directory)
        return True
    logger.warning("Mount %s ignorado: diretório ausente (%s)", route, directory)
    return False


mount_if_dir("/static", STATIC_DIR, "static")
mount_if_dir("/assets", WEB_STATIC_DIR, "assets")
mount_if_dir("/img/products", IMAGES_DIR, "product-images")


# ---------------------------------------------------------------------------
# Middleware do cookie cart_token
# ---------------------------------------------------------------------------
@app.middleware("http")
async def cart_cookie_middleware(request: Request, call_next):  # noqa: ANN001
    path = request.url.path
    token = request.cookies.get(CART_COOKIE) or ""
    new_token = False
    if not token:
        token = str(uuid.uuid4())
        new_token = True
    request.state.cart_token = token
    response = await call_next(request)
    is_asset = path.startswith(("/static/", "/assets/", "/img/"))
    set_cookie_header = response.headers.get("set-cookie", "")
    if not is_asset and (new_token or CART_COOKIE not in set_cookie_header):
        response.set_cookie(
            CART_COOKIE,
            token,
            max_age=CART_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return response


# ---------------------------------------------------------------------------
# Schemas (pydantic v2)
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=190)
    password: str = Field(min_length=6, max_length=72)
    cpf: str | None = Field(default=None, max_length=14)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("name", "email", "cpf", "phone", mode="before")
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Informe um e-mail válido")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Informe seu nome completo")
        return v.strip()


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email", mode="before")
    @classmethod
    def _lower(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class CartItemIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    qty: int = Field(default=1, ge=1, le=999)


class CartQtyIn(BaseModel):
    qty: int = Field(ge=-999, le=999)


class ShipIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=190)
    phone: str | None = Field(default=None, max_length=30)
    cep: str | None = Field(default=None, max_length=12)
    address: str | None = Field(default=None, max_length=190)
    number: str | None = Field(default=None, max_length=20)
    complement: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)


class CheckoutIn(BaseModel):
    payment: Literal["pix", "boleto", "cartao"]
    ship: ShipIn | None = None
    notes: str | None = Field(default=None, max_length=500)
    # Preço/frete enviados pelo cliente são IGNORADOS de propósito: tudo é calculado no servidor.
    shipping: Any = Field(default=None)


# ---------------------------------------------------------------------------
# Helpers: categorias
# ---------------------------------------------------------------------------
# O lower() do SQLite só rebaixa ASCII, então trocamos acentos nas DUAS caixas
# antes de aplicar lower() — assim a mesma expressão funciona em SQLite e Postgres.
_ACCENT_GROUPS = {
    "a": "áàâãäåÁÀÂÃÄÅ",
    "e": "éèêëÉÈÊË",
    "i": "íìîïÍÌÎÏ",
    "o": "óòôõöÓÒÔÕÖ",
    "u": "úùûüÚÙÛÜ",
    "c": "çÇ",
    "n": "ñÑ",
    "y": "ýÿÝŸ",
}
ACCENT_MAP = {ch: base for base, chars in _ACCENT_GROUPS.items() for ch in chars}


def fold_text(value: str | None) -> str:
    """Minúsculas e sem acento — mesma normalização usada no SQL de busca."""
    import unicodedata

    text = (value or "").strip().lower()
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return norm


def fold_sql(column):
    """Expressão SQL portável (SQLite e Postgres) que ignora caixa e acento."""
    expr = column
    for src, dst in ACCENT_MAP.items():
        expr = func.replace(expr, src, dst)
    return func.lower(expr)


def _slugify(value: str) -> str:
    import unicodedata

    norm = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return slug or "categoria"


def category_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Product.category_id, func.count(Product.id))
        .where(Product.active.is_(True), Product.category_id.is_not(None))
        .group_by(Product.category_id)
    ).all()
    return {cid: int(n) for cid, n in rows if cid}


def categories_payload(db: Session) -> list[dict]:
    """Lista de categorias com contagem agregada (inclui descendentes), ordenada por sort."""
    cats = list(db.scalars(select(Category).order_by(Category.sort, Category.name)))
    direct = category_counts(db)
    children: dict[str | None, list[Category]] = {}
    for c in cats:
        children.setdefault(c.parent_id, []).append(c)

    memo: dict[str, int] = {}

    def total(cat: Category) -> int:
        if cat.id in memo:
            return memo[cat.id]
        memo[cat.id] = 0  # guarda contra ciclo
        value = direct.get(cat.id, 0) + sum(total(ch) for ch in children.get(cat.id, []))
        memo[cat.id] = value
        return value

    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "parent_id": c.parent_id,
            "sort": c.sort,
            "count": total(c),
        }
        for c in cats
    ]


def find_category(db: Session, slug_or_id: str | None) -> Category | None:
    if not slug_or_id:
        return None
    key = slug_or_id.strip()
    cat = db.scalar(select(Category).where(Category.slug == key))
    if cat:
        return cat
    return db.get(Category, key)


def descendant_ids(db: Session, category: Category) -> list[str]:
    cats = list(db.scalars(select(Category)))
    children: dict[str | None, list[Category]] = {}
    for c in cats:
        children.setdefault(c.parent_id, []).append(c)
    out: list[str] = []

    def walk(cid: str) -> None:
        out.append(cid)
        for ch in children.get(cid, []):
            if ch.id not in out:
                walk(ch.id)

    walk(category.id)
    return out


# ---------------------------------------------------------------------------
# Helpers: carrinho
# ---------------------------------------------------------------------------
def request_cart_token(request: Request) -> str:
    return getattr(request.state, "cart_token", None) or request.cookies.get(CART_COOKIE) or str(uuid.uuid4())


def unique_cart_token(db: Session, desired: str) -> str:
    """Evita colisão de ``carts.token`` (cookie de um visitante que já virou carrinho
    de outro usuário no mesmo browser, ex.: duas contas na mesma máquina)."""
    taken = db.scalar(select(Cart).where(Cart.token == desired))
    return desired if taken is None else str(uuid.uuid4())


def resolve_cart(db: Session, request: Request, user: User | None) -> Cart:
    """Carrinho do usuário quando logado; senão o carrinho anônimo do cookie."""
    token = request_cart_token(request)
    if user is not None:
        cart = db.scalar(select(Cart).where(Cart.user_id == user.id).order_by(Cart.id))
        if cart is not None:
            return cart
        anon = db.scalar(select(Cart).where(Cart.token == token))
        if anon is not None and anon.user_id in (None, user.id):
            anon.user_id = user.id
            db.commit()
            return anon
        cart = Cart(token=unique_cart_token(db, token), user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
        return cart

    cart = db.scalar(select(Cart).where(Cart.token == token))
    if cart is None:
        cart = Cart(token=token)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def merge_carts(db: Session, anon_token: str, user: User) -> Cart:
    """Funde o carrinho anônimo (cookie) no carrinho do usuário logado."""
    user_cart = db.scalar(select(Cart).where(Cart.user_id == user.id).order_by(Cart.id))
    anon = db.scalar(select(Cart).where(Cart.token == anon_token))

    if anon is None or (user_cart is not None and anon.id == user_cart.id):
        return user_cart if user_cart is not None else resolve_cart_by_token(db, anon_token, user)

    if anon.user_id is not None and anon.user_id != user.id:
        # carrinho pertence a outro usuário: não sequestrar
        return user_cart if user_cart is not None else resolve_cart_by_token(db, anon_token, user)

    if user_cart is None:
        anon.user_id = user.id
        anon.updated_at = utcnow()
        db.commit()
        db.refresh(anon)
        return anon

    for item in list(anon.items):
        existing = db.scalar(
            select(CartItem).where(
                CartItem.cart_id == user_cart.id, CartItem.product_id == item.product_id
            )
        )
        if existing is not None:
            existing.qty = min(existing.qty + item.qty, 999)
        else:
            user_cart.items.append(CartItem(product_id=item.product_id, qty=item.qty))
    anon.items.clear()
    user_cart.updated_at = utcnow()
    db.flush()
    db.delete(anon)
    db.commit()
    db.refresh(user_cart)
    return user_cart


def resolve_cart_by_token(db: Session, token: str, user: User) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id).order_by(Cart.id))
    if cart is not None:
        return cart
    cart = db.scalar(select(Cart).where(Cart.token == token))
    if cart is None:
        cart = Cart(token=unique_cart_token(db, token), user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    elif cart.user_id is None:
        cart.user_id = user.id
        db.commit()
    return cart


def unit_price(product: Product) -> Decimal:
    """Preço efetivo SEMPRE vindo do banco (promoção quando válida)."""
    if product.sale_price is not None and Decimal(product.sale_price) > 0:
        return money(product.sale_price)
    return money(product.price)


def cart_payload(db: Session, cart: Cart) -> dict:
    rows = db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    ).all()
    items: list[dict] = []
    subtotal = Decimal("0.00")
    count = 0
    for cart_item, product in rows:
        if product is None:
            continue
        price = unit_price(product)
        line = money(price * cart_item.qty)
        subtotal += line
        count += cart_item.qty
        items.append(
            {
                "product_id": product.id,
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "sku": product.sku or product.id,
                "brand": product.brand,
                "unit": product.unit,
                "price": float(price),
                "list_price": as_float(product.price),
                "sale_price": as_float(product.sale_price) if product.sale_price is not None else None,
                "qty": cart_item.qty,
                "quantity": cart_item.qty,
                "subtotal": float(line),
                "total": float(line),
                "image_url": image_url(product.image_path),
                "max_qty": product.max_qty or 999,
                "stock": product.stock,
                "in_stock": (product.stock or "").strip().lower().startswith("dispon"),
            }
        )
    return {
        "id": cart.id,
        "token": cart.token,
        "items": items,
        "count": count,
        "subtotal": float(money(subtotal)),
        "total": float(money(subtotal)),
        "shipping": 0.0,
    }


EMPTY_CART = {"id": None, "token": "", "items": [], "count": 0, "subtotal": 0.0, "total": 0.0, "shipping": 0.0}


def apply_cart_cookie(response: Response, cart: Cart) -> None:
    response.set_cookie(
        CART_COOKIE,
        cart.token,
        max_age=CART_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


# ---------------------------------------------------------------------------
# Helpers: catálogo
# ---------------------------------------------------------------------------
SORTS = ("relevance", "price_asc", "price_desc", "name", "newest")

# Ordem fixa da navegação do site original (o banco pode ter centenas de categorias)
NAV_IDS = [
    "BOVINOS",
    "BOVINOS_IMPORTADOS",
    "AVES",
    "SUINOS",
    "PESCADOS",
    "BATATAS_E_VEGETAIS",
    "CORDEIROS",
    "CHARQUE",
    "Outros_Produtos",
    "MARCAS",
]


def _flag(value: str | None) -> bool:
    return str(value).strip().lower() in ("1", "true", "t", "yes", "y", "on") if value is not None else False


def price_expr():
    return func.coalesce(Product.sale_price, Product.price)


def query_products(
    db: Session,
    *,
    q: str | None = None,
    category: Category | None = None,
    page: int = 1,
    limit: int = 12,
    sort: str = "relevance",
    on_sale: bool = False,
    in_stock: bool = False,
) -> dict:
    stmt = select(Product).where(Product.active.is_(True))
    count_stmt = select(func.count(Product.id)).where(Product.active.is_(True))

    if category is not None:
        ids = descendant_ids(db, category)
        stmt = stmt.where(Product.category_id.in_(ids))
        count_stmt = count_stmt.where(Product.category_id.in_(ids))

    term = fold_text(q)
    if term:
        like = f"%{term}%"
        cond = or_(
            fold_sql(Product.name).like(like),
            fold_sql(func.coalesce(Product.brand, "")).like(like),
            fold_sql(func.coalesce(Product.sku, "")).like(like),
            fold_sql(func.coalesce(Product.ean, "")).like(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if on_sale:
        cond = Product.sale_price.is_not(None)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if in_stock:
        cond = func.lower(Product.stock).like("dispon%")
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    sort = sort if sort in SORTS else "relevance"
    in_stock_rank = case((func.lower(Product.stock).like("dispon%"), 0), else_=1)
    if sort == "price_asc":
        stmt = stmt.order_by(price_expr().asc(), func.lower(Product.name))
    elif sort == "price_desc":
        stmt = stmt.order_by(price_expr().desc(), func.lower(Product.name))
    elif sort == "name":
        stmt = stmt.order_by(func.lower(Product.name).asc())
    elif sort == "newest":
        stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc())
    else:
        if term:
            prefix = case((fold_sql(Product.name).like(f"{term}%"), 0), else_=1)
            stmt = stmt.order_by(prefix, in_stock_rank, func.lower(Product.name))
        else:
            stmt = stmt.order_by(in_stock_rank, func.lower(Product.name))

    total = int(db.scalar(count_stmt) or 0)
    limit = max(1, min(int(limit or 12), 100))
    pages = max(1, math.ceil(total / limit)) if total else 1
    page = max(1, min(int(page or 1), pages))
    rows = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()

    return {
        "items": [p.as_dict() for p in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "sort": sort,
        "on_sale": bool(on_sale),
        "in_stock": bool(in_stock),
        "q": q or "",
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_page": max(1, page - 1),
        "next_page": min(pages, page + 1),
    }


def find_product(db: Session, slug_or_id: str) -> Product | None:
    key = (slug_or_id or "").strip()
    if not key:
        return None
    product = db.scalar(select(Product).where(Product.slug == key, Product.active.is_(True)))
    if product is not None:
        return product
    product = db.get(Product, key)
    if product is not None and product.active:
        return product
    return None


def best_sellers(db: Session, limit: int = 8) -> list[Product]:
    sold = (
        select(OrderItem.product_id, func.sum(OrderItem.qty).label("sold"))
        .where(OrderItem.product_id.is_not(None))
        .group_by(OrderItem.product_id)
        .subquery()
    )
    rows = db.execute(
        select(Product, func.coalesce(sold.c.sold, 0).label("sold"))
        .outerjoin(sold, Product.id == sold.c.product_id)
        .where(Product.active.is_(True))
        .order_by(
            func.coalesce(sold.c.sold, 0).desc(),
            case((func.lower(Product.stock).like("dispon%"), 0), else_=1),
            func.lower(Product.name),
        )
        .limit(limit)
    ).all()
    return [row[0] for row in rows]


def newest_products(db: Session, limit: int = 8) -> list[Product]:
    return list(
        db.scalars(
            select(Product)
            .where(Product.active.is_(True))
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(limit)
        )
    )


def sale_products(db: Session, limit: int = 8) -> list[Product]:
    return list(
        db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.sale_price.is_not(None))
            .order_by(price_expr().asc(), func.lower(Product.name))
            .limit(limit)
        )
    )


def related_products(db: Session, product: Product, limit: int = 8) -> list[Product]:
    rows: list[Product] = []
    if product.category_id:
        rows = list(
            db.scalars(
                select(Product)
                .where(
                    Product.active.is_(True),
                    Product.category_id == product.category_id,
                    Product.id != product.id,
                )
                .order_by(func.lower(Product.name))
                .limit(limit)
            )
        )
    if len(rows) < limit:
        ids = [p.id for p in rows] + [product.id]
        extra = db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.id.not_in(ids))
            .order_by(case((func.lower(Product.stock).like("dispon%"), 0), else_=1), func.lower(Product.name))
            .limit(limit - len(rows))
        )
        rows.extend(extra)
    return rows[:limit]


# ---------------------------------------------------------------------------
# Helpers: pedidos
# ---------------------------------------------------------------------------
def order_payload(order: Order) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "subtotal": as_float(order.subtotal),
        "shipping": as_float(order.shipping),
        "total": as_float(order.total),
        "payment": order.payment,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "ship": {
            "name": order.ship_name,
            "email": order.ship_email,
            "phone": order.ship_phone,
            "cep": order.ship_cep,
            "address": order.ship_address,
            "number": order.ship_number,
            "complement": order.ship_complement,
            "district": order.ship_district,
            "city": order.ship_city,
            "state": order.ship_state,
        },
        "items": [
            {
                "product_id": item.product_id,
                "name": item.name,
                "unit_price": as_float(item.unit_price),
                "qty": item.qty,
                "subtotal": as_float(item.subtotal),
            }
            for item in order.items
        ],
    }


# ---------------------------------------------------------------------------
# Renderização de páginas
# ---------------------------------------------------------------------------
def base_context(request: Request, db: Session, user: User | None) -> dict:
    cats = categories_payload(db)
    by_id = {c["id"]: c for c in cats}
    nav = [by_id[cat_id] for cat_id in NAV_IDS if cat_id in by_id]
    if not nav:  # banco fora do padrão: cai para as raízes com produtos
        roots = [c for c in cats if not c["parent_id"]]
        nav = [c for c in roots if c["count"] > 0] or roots[:12]
    cart = resolve_cart(db, request, user)
    cart_data = cart_payload(db, cart) if cart is not None else dict(EMPTY_CART)
    return {
        "request": request,
        "categories": cats,
        "nav_categories": nav,
        "nav": nav,
        "cart": cart_data,
        "cart_count": cart_data["count"],
        "user": user.as_dict() if user is not None else None,
        "user_obj": user,
        "current_path": request.url.path,
        "current_url": str(request.url),
        "year": datetime.now().year,
        "store_name": STORE_NAME,
        "page_title": None,
        "meta_description": "Friboi Online — carnes e produtos para o seu negócio.",
    }


FALLBACK_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:sans-serif;padding:32px">
<h1>{title}</h1><p>{msg}</p>
<p><a href="/">Voltar para a loja</a></p>
</body></html>"""


def render(
    request: Request,
    template: str,
    *,
    db: Session,
    user: User | None,
    status_code: int = 200,
    **context: Any,
) -> HTMLResponse:
    """Renderiza um template injetando o contexto base comum a todas as páginas."""
    ctx = base_context(request, db, user)
    ctx.update(context)
    try:
        return templates.TemplateResponse(
            request=request, name=template, context=ctx, status_code=status_code
        )
    except TemplateNotFound:
        logger.error("Template ausente: %s (aguardando server/templates/ — T4)", template)
        return HTMLResponse(
            FALLBACK_HTML.format(
                title="Template ausente",
                msg=f"O template <code>{template}</code> ainda não existe em server/templates/.",
            ),
            status_code=500,
        )


def user_or_none(request: Request, db: Session) -> User | None:
    return auth.optional_user(request, db)


# ===========================================================================
# PÁGINAS
# ===========================================================================
@app.get("/", response_class=HTMLResponse)
def page_index(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = user_or_none(request, db)
    lancamentos = newest_products(db, 8)
    promocoes = sale_products(db, 8)
    mais_vendidos = best_sellers(db, 8)
    sugestao = sale_products(db, 8) if promocoes else newest_products(db, 8)
    vitrines = [
        {
            "slug": "negocios-como-o-seu",
            "titulo": "Negócios Como O Seu Compraram",
            "produtos": [p.as_dict() for p in mais_vendidos],
        },
        {
            "slug": "sugestao-para-o-seu-negocio",
            "titulo": "Sugestão Para O Seu Negócio",
            "produtos": [p.as_dict() for p in (sugestao or lancamentos)],
        },
    ]
    cats = categories_payload(db)
    return render(
        request,
        "index.html",
        db=db,
        user=user,
        page_title=STORE_NAME,
        lancamentos=[p.as_dict() for p in lancamentos],
        promocoes=[p.as_dict() for p in promocoes],
        mais_vendidos=[p.as_dict() for p in mais_vendidos],
        sugestao=[p.as_dict() for p in (sugestao or lancamentos)],
        vitrines=vitrines,
        destaques=[p.as_dict() for p in lancamentos],
        categorias_destaque=[c for c in cats if not c["parent_id"] and c["count"] > 0],
        brands=["Friboi", "Chef", "Maturatta", "Black Friboi", "1953"],
        cards_marca=[
            {"nome": "Costela", "slug": "costela", "categoria": "bovinos"},
            {"nome": "Picanha", "slug": "picanha", "categoria": "bovinos"},
            {"nome": "Contrafilé", "slug": "contrafile", "categoria": "bovinos"},
            {"nome": "Coxão mole", "slug": "coxao-mole", "categoria": "bovinos"},
            {"nome": "Pescados", "slug": "pescados", "categoria": "pescados"},
            {"nome": "Batatas", "slug": "batatas", "categoria": "batatas-e-vegetais"},
        ],
        beneficios=[
            {"titulo": "Entrega para todo o Brasil", "texto": "Receba no seu estabelecimento com agilidade."},
            {"titulo": "Preço de atacado", "texto": "Condições especiais para o seu negócio."},
            {"titulo": "Qualidade Friboi", "texto": "Carnes selecionadas e rastreadas."},
            {"titulo": "Compra segura", "texto": "Pagamento protegido em ambiente criptografado."},
        ],
    )


def _catalogo_page(
    request: Request,
    db: Session,
    *,
    user: User | None,
    categoria: Category | None,
    q: str | None,
    page: int,
    sort: str,
    on_sale: bool,
    in_stock: bool,
    titulo: str,
):
    limit = 12
    data = query_products(
        db,
        q=q,
        category=categoria,
        page=page,
        limit=limit,
        sort=sort,
        on_sale=on_sale,
        in_stock=in_stock,
    )
    cat_dict = None
    if categoria is not None:
        cat_dict = next(
            (c for c in categories_payload(db) if c["id"] == categoria.id),
            {
                "id": categoria.id,
                "name": categoria.name,
                "slug": categoria.slug,
                "parent_id": categoria.parent_id,
                "sort": categoria.sort,
                "count": data["total"],
            },
        )
    filters = {
        "q": q or "",
        "sort": data["sort"],
        "on_sale": on_sale,
        "in_stock": in_stock,
        "category": cat_dict["slug"] if cat_dict else "",
    }
    return render(
        request,
        "catalogo.html",
        db=db,
        user=user,
        page_title=titulo,
        titulo=titulo,
        title=titulo,
        categoria=cat_dict,
        category=cat_dict,
        items=data["items"],
        products=data["items"],
        total=data["total"],
        page=data["page"],
        limit=data["limit"],
        pages=data["pages"],
        sort=data["sort"],
        on_sale=on_sale,
        in_stock=in_stock,
        q=q or "",
        filtros=filters,
        filters=filters,
        has_prev=data["has_prev"],
        has_next=data["has_next"],
        prev_page=data["prev_page"],
        next_page=data["next_page"],
        base_url=request.url.path,
        query_string=request.url.query,
    )


@app.get("/categoria/{slug}", response_class=HTMLResponse)
def page_categoria(
    request: Request,
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    sort: str = "relevance",
    on_sale: str | None = None,
    in_stock: str | None = None,
    q: str | None = None,
):
    user = user_or_none(request, db)
    categoria = find_category(db, slug)
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return _catalogo_page(
        request,
        db,
        user=user,
        categoria=categoria,
        q=q,
        page=page,
        sort=sort,
        on_sale=_flag(on_sale),
        in_stock=_flag(in_stock),
        titulo=categoria.name,
    )


@app.get("/busca", response_class=HTMLResponse)
def page_busca(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: str = "",
    page: int = Query(1, ge=1),
    sort: str = "relevance",
    on_sale: str | None = None,
    in_stock: str | None = None,
):
    user = user_or_none(request, db)
    titulo = f'Resultados para "{q.strip()}"' if q and q.strip() else "Busca"
    return _catalogo_page(
        request,
        db,
        user=user,
        categoria=None,
        q=q,
        page=page,
        sort=sort,
        on_sale=_flag(on_sale),
        in_stock=_flag(in_stock),
        titulo=titulo,
    )


@app.get("/promocoes", response_class=HTMLResponse)
def page_promocoes(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    sort: str = "relevance",
    in_stock: str | None = None,
    q: str | None = None,
):
    user = user_or_none(request, db)
    return _catalogo_page(
        request,
        db,
        user=user,
        categoria=None,
        q=q,
        page=page,
        sort=sort,
        on_sale=True,
        in_stock=_flag(in_stock),
        titulo="Promoções",
    )


@app.get("/produto/{slug}", response_class=HTMLResponse)
def page_produto(request: Request, slug: str, db: Annotated[Session, Depends(get_db)]):
    user = user_or_none(request, db)
    product = find_product(db, slug)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    categoria_obj = db.get(Category, product.category_id) if product.category_id else None
    cat_dict = None
    if categoria_obj is not None:
        cat_dict = next(
            (c for c in categories_payload(db) if c["id"] == categoria_obj.id),
            categoria_obj.as_dict(),
        )
    data = product.as_dict(full=True)
    breadcrumb = [{"label": "Home", "url": "/"}]
    if cat_dict:
        breadcrumb.append({"label": cat_dict["name"], "url": f"/categoria/{cat_dict['slug']}"})
    breadcrumb.append({"label": product.name, "url": f"/produto/{product.slug}"})
    related = related_products(db, product, 8)
    max_qty = max(1, min(int(product.max_qty or 1), 20))
    return render(
        request,
        "produto.html",
        db=db,
        user=user,
        page_title=f"{product.name} | {STORE_NAME}",
        produto=data,
        product=data,
        p=data,
        categoria=cat_dict,
        category=cat_dict,
        breadcrumb=breadcrumb,
        relacionados=[p.as_dict() for p in related],
        related=[p.as_dict() for p in related],
        images=data["images"],
        qty_options=list(range(1, max_qty + 1)),
    )


@app.get("/login", response_class=HTMLResponse)
def page_login(request: Request, db: Annotated[Session, Depends(get_db)], next: str = "/"):
    user = user_or_none(request, db)
    if user is not None:
        return RedirectResponse(url=next or "/", status_code=303)
    return render(
        request,
        "login.html",
        db=db,
        user=None,
        page_title=f"Entrar | {STORE_NAME}",
        next=next or "/",
        redirect_to=next or "/",
    )


@app.get("/cadastro", response_class=HTMLResponse)
def page_cadastro(request: Request, db: Annotated[Session, Depends(get_db)], next: str = "/"):
    user = user_or_none(request, db)
    if user is not None:
        return RedirectResponse(url=next or "/", status_code=303)
    return render(
        request,
        "cadastro.html",
        db=db,
        user=None,
        page_title=f"Criar conta | {STORE_NAME}",
        next=next or "/",
        redirect_to=next or "/",
    )


@app.get("/carrinho", response_class=HTMLResponse)
def page_carrinho(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = user_or_none(request, db)
    return render(
        request,
        "carrinho.html",
        db=db,
        user=user,
        page_title=f"Carrinho | {STORE_NAME}",
        frete=0.0,
        shipping=0.0,
    )


@app.get("/checkout", response_class=HTMLResponse)
def page_checkout(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = user_or_none(request, db)
    return render(
        request,
        "checkout.html",
        db=db,
        user=user,
        page_title=f"Finalizar compra | {STORE_NAME}",
        frete=0.0,
        shipping=0.0,
        requires_login=user is None,
        payments=[
            {"value": "pix", "label": "Pix"},
            {"value": "boleto", "label": "Boleto"},
            {"value": "cartao", "label": "Cartão de crédito"},
        ],
    )


@app.get("/conta", response_class=HTMLResponse)
def page_conta(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = user_or_none(request, db)
    if user is None:
        return RedirectResponse(url="/login?next=/conta", status_code=303)
    orders = list(
        db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc(), Order.id.desc()))
    )
    return render(
        request,
        "conta.html",
        db=db,
        user=user,
        page_title=f"Minha conta | {STORE_NAME}",
        pedidos=[order_payload(o) for o in orders],
        orders=[order_payload(o) for o in orders],
    )


@app.get("/404", response_class=HTMLResponse)
def page_404(request: Request, db: Annotated[Session, Depends(get_db)]):
    return render(
        request,
        "404.html",
        db=db,
        user=user_or_none(request, db),
        status_code=404,
        page_title=f"Página não encontrada | {STORE_NAME}",
    )


# ===========================================================================
# PÁGINAS INSTITUCIONAIS (/institucional/{slug}) — links do rodapé
# ===========================================================================
PAGINAS_INSTITUCIONAIS: dict[str, dict] = {
    "login-cadastro": {
        "titulo": "Login ou Cadastre-se",
        "html": (
            "<p>Para comprar no Friboi Online você precisa ter uma conta. O cadastro é gratuito, "
            "leva menos de dois minutos e libera a tabela de preços, o histórico de pedidos e as "
            "condições da sua região.</p>"
            "<p>Com a conta ativa você acompanha pedidos, salva seus endereços de entrega e recebe "
            "as ofertas da sua unidade de atendimento.</p>"
            '<p><a href="/cadastro">Criar minha conta</a> &middot; <a href="/login">Já tenho conta</a></p>'
        ),
        "paragrafos": [
            "Para comprar no Friboi Online você precisa ter uma conta. O cadastro é gratuito e leva menos de dois minutos.",
            "Com a conta ativa você acompanha pedidos, salva endereços de entrega e recebe as ofertas da sua unidade.",
        ],
    },
    "unidades": {
        "titulo": "Unidades de Atendimento",
        "html": (
            "<p>O Friboi Online atende estabelecimentos comerciais em todo o Brasil por meio de "
            "unidades regionais de atendimento. Cada unidade tem o seu próprio mix de produtos, "
            "tabela de preços e calendário de entregas.</p>"
            "<p>Ao se cadastrar, sua conta é vinculada à unidade que atende o CEP do seu negócio. "
            "Se precisar trocar de unidade, fale com o nosso time pelo telefone ou WhatsApp do "
            "atendimento da sua região.</p>"
            "<p>Consulte as unidades e os horários na página de <a href=\"/unidades\">atendimento</a> "
            "ou entre em contato pela <a href=\"/conta\">sua conta</a>.</p>"
        ),
        "paragrafos": [
            "O Friboi Online atende estabelecimentos comerciais em todo o Brasil por meio de unidades regionais.",
            "Cada unidade tem o seu próprio mix de produtos, tabela de preços e calendário de entregas.",
        ],
    },
    "boleto": {
        "titulo": "Seguindo via Boleto",
        "html": (
            "<p>Pedidos pagos por boleto são confirmados após a compensação bancária, que pode levar "
            "até dois dias úteis. O boleto é enviado para o e-mail cadastrado no momento da compra "
            "e também fica disponível em <a href=\"/conta\">Minha conta &rsaquo; Pedidos</a>.</p>"
            "<p>O prazo de entrega começa a contar somente depois da confirmação do pagamento. "
            "Boletos vencidos não são compensados: se precisar de uma segunda via, gere novamente "
            "pelo detalhe do pedido.</p>"
            "<p>Dúvidas sobre o seu boleto? Fale com o atendimento da sua unidade de atendimento.</p>"
        ),
        "paragrafos": [
            "Pedidos pagos por boleto são confirmados após a compensação bancária, que pode levar até dois dias úteis.",
            "O prazo de entrega começa a contar somente depois da confirmação do pagamento.",
        ],
    },
    "exclusao-conta": {
        "titulo": "Exclusão e Cancelamento de Conta",
        "html": (
            "<p>Você pode solicitar a exclusão ou o cancelamento da sua conta a qualquer momento. "
            "Pedidos em andamento precisam ser concluídos ou cancelados antes da exclusão, para que "
            "não fiquem pendências de entrega ou cobrança.</p>"
            "<p>Para solicitar, envie um e-mail para o atendimento informando o nome do "
            "estabelecimento e o e-mail cadastrado, ou use a opção de atendimento em "
            "<a href=\"/conta\">Minha conta</a>. A solicitação é processada em até cinco dias úteis.</p>"
            "<p>Dados fiscais de pedidos já concluídos são mantidos pelo prazo legal exigido.</p>"
        ),
        "paragrafos": [
            "Você pode solicitar a exclusão ou o cancelamento da sua conta a qualquer momento.",
            "Pedidos em andamento precisam ser concluídos antes da exclusão para evitar pendências.",
        ],
    },
    "entregas": {
        "titulo": "Entregas",
        "html": (
            "<p>Cada unidade de atendimento define a sua região de entrega, os dias de "
            "carregamento e o valor do frete. O prazo é informado no <a href=\"/checkout\">checkout</a> "
            "antes de você concluir o pedido.</p>"
            "<p>As carnes são transportadas em temperatura controlada. No recebimento, confira a "
            "embalagem e a nota fiscal com o motorista; qualquer divergência deve ser registrada na "
            "hora da entrega.</p>"
            "<p>Para reagendar uma entrega, fale com o atendimento da sua unidade com pelo menos um "
            "dia útil de antecedência.</p>"
        ),
        "paragrafos": [
            "Cada unidade define a região de entrega, os dias de carregamento e o valor do frete.",
            "O prazo de entrega é informado no checkout antes de concluir o pedido.",
        ],
    },
    "marcas": {
        "titulo": "Nossas Marcas",
        "html": (
            "<p>O Friboi Online reúne as principais marcas de carne e vegetais para o seu negócio: "
            "Friboi, Friboi Chef, Maturatta, Black Friboi, 1953 e Seara, além da linha de Pescados.</p>"
            "<p>Cada marca tem o seu posicionamento: do corte tradicional do dia a dia às peças "
            "premium para churrasco e à praticidade dos congelados.</p>"
            '<ul class="brand-list">'
            '<li><a href="/busca?q=friboi">Friboi</a></li>'
            '<li><a href="/busca?q=chef">Do Chef</a></li>'
            '<li><a href="/busca?q=maturatta">Maturatta</a></li>'
            '<li><a href="/busca?q=black">Black Friboi</a></li>'
            '<li><a href="/busca?q=1953">1953</a></li>'
            '</ul>'
        ),
        "paragrafos": [
            "O Friboi Online reúne as principais marcas de carne para o seu negócio.",
            "Do corte tradicional às peças premium, cada marca tem o seu posicionamento.",
        ],
    },
    "nossa-historia": {
        "titulo": "Nossa História",
        "html": (
            "<p>O Friboi Online nasceu para simplificar a compra de carne no atacado: a mesma "
            "qualidade das grandes marcas da JBS, com a praticidade de comprar de onde você estiver.</p>"
            "<p>A plataforma reúne o portfólio das unidades regionais em um só lugar, com tabela de "
            "preços para o seu negócio, pedido em poucos cliques e logística refrigerada até a "
            "porta do seu estabelecimento.</p>"
            "<p>Somos a loja de quem vive de carne: açougues, restaurantes, hamburguerias, "
            "rotisseries, cozinhas industriais e distribuidores.</p>"
        ),
        "paragrafos": [
            "O Friboi Online simplifica a compra de carne no atacado, com a qualidade das marcas da JBS.",
            "Reunimos o portfólio das unidades regionais com preço para o seu negócio e entrega refrigerada.",
        ],
    },
    "privacidade": {
        "titulo": "Política de Privacidade",
        "html": (
            "<p>Coletamos apenas os dados necessários para atender o seu negócio: identificação, "
            "contato, endereço de entrega e histórico de pedidos. Esses dados são usados para "
            "processar compras, emitir nota fiscal e melhorar a sua experiência no site.</p>"
            "<p>Não vendemos seus dados. Eles são compartilhados somente com quem é necessário para "
            "a entrega e o pagamento, sempre de acordo com a Lei Geral de Proteção de Dados "
            "(LGPD &mdash; Lei 13.709/2018).</p>"
            "<p>Você pode solicitar acesso, correção ou exclusão dos seus dados pelo atendimento. "
            "Cookies e tecnologias semelhantes são tratados na <a href=\"/institucional/politica-de-cookies\">Política de Cookies</a>.</p>"
        ),
        "paragrafos": [
            "Coletamos apenas os dados necessários para atender o seu negócio: identificação, contato, endereço e histórico de pedidos.",
            "Não vendemos seus dados. O compartilhamento ocorre só com quem é necessário para entrega e pagamento, conforme a LGPD.",
        ],
    },
    "cookies": {
        "titulo": "Política de Cookies",
        "html": (
            "<p>Usamos cookies para manter a sua sessão, guardar o carrinho entre uma visita e outra "
            "e entender quais páginas são mais úteis. Os cookies essenciais são necessários para o "
            "site funcionar e não podem ser desativados.</p>"
            "<p>Não usamos cookies para vender informação a terceiros. Você pode bloquear ou apagar "
            "cookies nas configurações do navegador &mdash; ao fazer isso, o carrinho e o login "
            "podem deixar de funcionar corretamente.</p>"
            "<p>Dúvidas sobre cookies e dados pessoais estão na <a href=\"/institucional/politica-de-privacidade\">Política de Privacidade</a>.</p>"
        ),
        "paragrafos": [
            "Usamos cookies para manter a sessão, guardar o carrinho e entender quais páginas são mais úteis.",
            "Os cookies essenciais não podem ser desativados; sem eles o carrinho e o login não funcionam.",
        ],
    },
    "mapa-do-site": {"titulo": "Mapa do Site", "html": "", "paragrafos": []},
    "faq": {
        "titulo": "FAQ",
        "html": (
            "<h3>Preciso ter CNPJ para comprar?</h3>"
            "<p>Sim. O Friboi Online atende exclusivamente estabelecimentos comerciais, com pedido "
            "mínimo e condições definidos pela unidade de atendimento da sua região.</p>"
            "<h3>Como vejo o preço dos produtos?</h3>"
            "<p>A tabela de preços aparece depois do login, de acordo com a unidade que atende o seu "
            "CEP. Antes disso o site mostra o valor de referência.</p>"
            "<h3>Quais são as formas de pagamento?</h3>"
            "<p>Pix, boleto bancário e cartão de crédito, conforme as condições da sua unidade.</p>"
            "<h3>Como acompanho meu pedido?</h3>"
            "<p>Em <a href=\"/conta\">Minha conta &rsaquo; Pedidos</a> você vê o status, os itens e os "
            "dados de entrega de cada pedido.</p>"
            "<h3>Posso trocar ou devolver um produto?</h3>"
            "<p>Sim. Registre a divergência no momento da entrega e fale com o atendimento em até "
            "72 horas para avaliarmos a troca ou o estorno.</p>"
        ),
        "paragrafos": [
            "O Friboi Online atende exclusivamente estabelecimentos comerciais (CNPJ).",
            "A tabela de preços aparece depois do login, conforme a unidade que atende o seu CEP.",
            "Formas de pagamento: Pix, boleto e cartão de crédito.",
        ],
    },
    # Marca por marca (links do rodapé: Nossas Marcas)
    "marca-friboi": {
        "titulo": "Friboi",
        "html": (
            "<p>A marca Friboi é sinônimo de carne bovina de qualidade para o dia a dia do seu "
            "negócio: cortes dianteiros, traseiros, costelas e miúdos, com padrão de corte constante.</p>"
            '<p><a href="/busca?q=friboi">Ver produtos Friboi</a></p>'
        ),
        "paragrafos": ["Carne bovina de qualidade para o dia a dia do seu negócio."],
    },
    "marca-maturatta": {
        "titulo": "Maturatta",
        "html": (
            "<p>Maturatta é a linha de carnes maturadas, com mais maciez e sabor para quem quer "
            "elevar o nível do cardápio.</p>"
            '<p><a href="/busca?q=maturatta">Ver produtos Maturatta</a></p>'
        ),
        "paragrafos": ["Carnes maturadas, com mais maciez e sabor."],
    },
    "marca-do-chef": {
        "titulo": "Do Chef",
        "html": (
            "<p>Do Chef é a linha pensada para a rotina de cozinha profissional: porções práticas, "
            "congelados de qualidade e cortes prontos para o preparo.</p>"
            '<p><a href="/busca?q=chef">Ver produtos Do Chef</a></p>'
        ),
        "paragrafos": ["Porções práticas e congelados de qualidade para a cozinha profissional."],
    },
    "marca-black-friboi": {
        "titulo": "Black Friboi",
        "html": (
            "<p>Black Friboi é a seleção premium: cortes nobres, maturação controlada e "
            "apresentação especial para os pratos mais exigentes.</p>"
            '<p><a href="/busca?q=black">Ver produtos Black Friboi</a></p>'
        ),
        "paragrafos": ["Seleção premium de cortes nobres com maturação controlada."],
    },
    "marca-1953": {
        "titulo": "1953",
        "html": (
            "<p>A linha 1953 celebra a tradição do churrasco brasileiro, com cortes selecionados "
            "e porcionados para o seu negócio.</p>"
            '<p><a href="/busca?q=1953">Ver produtos 1953</a></p>'
        ),
        "paragrafos": ["Cortes selecionados e porcionados para o churrasco."],
    },
}

# Slug canônico -> slug que o template institucional.html (T4) conhece, para que
# páginas acessadas pelo slug canônico também renderizem o texto completo.
INSTITUCIONAL_TEMPLATE_SLUG: dict[str, str] = {
    "login-cadastro": "login-ou-cadastre-se",
    "boleto": "segunda-via-boleto",
    "exclusao-conta": "exclusao-cancelamento-conta",
    "privacidade": "politica-de-privacidade",
    "cookies": "politica-de-cookies",
}

# Slugs alternativos (links antigos / variações) -> slug canônico
INSTITUCIONAL_ALIASES: dict[str, str] = {
    "login-ou-cadastre-se": "login-cadastro",
    "segunda-via-boleto": "boleto",
    "exclusao-cancelamento-conta": "exclusao-conta",
    "politica-de-privacidade": "privacidade",
    "politica-de-cookies": "cookies",
    "quemsomos": "nossa-historia",
    "quem-somos": "nossa-historia",
}


def _mapa_do_site(db: Session) -> tuple[str, list[str]]:
    """Conteúdo dinâmico do Mapa do Site (categorias com produtos + páginas)."""
    from xml.sax.saxutils import escape as _esc

    cats = categories_payload(db)
    roots = [c for c in cats if not c["parent_id"] and c["count"] > 0]
    links = "".join(
        f'<li><a href="/categoria/{_esc(c["slug"])}">{_esc(c["name"])}</a> '
        f'({c["count"]} produtos)</li>'
        for c in roots
    )
    html = (
        "<p>Páginas principais:</p><ul>"
        '<li><a href="/">Home</a></li>'
        '<li><a href="/promocoes">Promoções</a></li>'
        '<li><a href="/busca">Busca</a></li>'
        '<li><a href="/carrinho">Carrinho</a></li>'
        '<li><a href="/conta">Minha conta</a></li>'
        "</ul>"
        f"<p>Categorias:</p><ul>{links}</ul>"
    )
    paragrafos = ["Páginas principais da loja e todas as categorias com produtos disponíveis."]
    return html, paragrafos


@app.get("/institucional/{slug}", response_class=HTMLResponse)
def page_institucional(slug: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Páginas institucionais dos links do rodapé. Slug desconhecido -> 404."""
    canonical = INSTITUCIONAL_ALIASES.get(slug, slug)
    pagina = PAGINAS_INSTITUCIONAIS.get(canonical)
    if pagina is None:
        raise HTTPException(status_code=404, detail="Página não encontrada")
    titulo = pagina["titulo"]
    conteudo = pagina["html"]
    paragrafos = list(pagina.get("paragrafos") or [])
    if canonical == "mapa-do-site":
        conteudo, paragrafos = _mapa_do_site(db)
    # `slug` é o que o template usa para escolher o texto; para os slugs canônicos
    # mandamos o equivalente que o template conhece (senão ele cairia no texto genérico).
    template_slug = INSTITUCIONAL_TEMPLATE_SLUG.get(canonical, canonical)
    return render(
        request,
        "institucional.html",
        db=db,
        user=user_or_none(request, db),
        page_title=f"{titulo} | {STORE_NAME}",
        slug=template_slug,
        slug_solicitado=slug,
        slug_canonico=canonical,
        titulo=titulo,
        titulo_pagina=titulo,
        conteudo=conteudo,
        paragrafos=paragrafos,
    )


# ===========================================================================
# SEO de cortesia: sitemap.xml + robots.txt
# ===========================================================================
def site_base_url(request: Request) -> str:
    """URL base absoluta do site (respeita SITE_URL em produção/CDN)."""
    base = (os.environ.get("SITE_URL") or "").strip() or str(request.base_url)
    return base.rstrip("/") + "/"


@app.get("/sitemap.xml", response_class=Response, include_in_schema=False)
def sitemap_xml(request: Request, db: Annotated[Session, Depends(get_db)]):
    from xml.sax.saxutils import escape as _esc

    base = site_base_url(request)
    urls = [base]
    for cat in db.scalars(select(Category).order_by(Category.sort, Category.name)):
        urls.append(f"{base}categoria/{cat.slug}")
    for product in db.scalars(
        select(Product).where(Product.active.is_(True)).order_by(Product.id)
    ):
        urls.append(f"{base}produto/{product.slug}")

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{_esc(url)}</loc></url>\n" for url in urls)
        + "</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt(request: Request):
    base = site_base_url(request)
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /carrinho\n"
        "Disallow: /checkout\n"
        "Disallow: /conta\n"
        "\n"
        f"Sitemap: {base}sitemap.xml\n"
    )
    return PlainTextResponse(content=body)


# ===========================================================================
# API — AUTENTICAÇÃO
# ===========================================================================
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def api_register(payload: RegisterIn, request: Request, response: Response, db: Annotated[Session, Depends(get_db)]):
    existing = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=auth.hash_password(payload.password),
        cpf=payload.cpf,
        phone=payload.phone,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth.create_access_token(user)
    auth.set_auth_cookie(response, token)
    try:
        cart = merge_carts(db, request_cart_token(request), user)
        apply_cart_cookie(response, cart)
        cart_data = cart_payload(db, cart)
    except Exception:  # noqa: BLE001 - merge nunca deve derrubar o cadastro
        logger.exception("Falha ao fundir carrinho no cadastro")
        cart_data = dict(EMPTY_CART)
    return {
        "user": user.as_dict(),
        "access_token": token,
        "token_type": "bearer",
        "cart": cart_data,
    }


@app.post("/api/auth/login")
def api_login(payload: LoginIn, request: Request, response: Response, db: Annotated[Session, Depends(get_db)]):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    if user is None or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    token = auth.create_access_token(user)
    auth.set_auth_cookie(response, token)
    try:
        cart = merge_carts(db, request_cart_token(request), user)
        apply_cart_cookie(response, cart)
        cart_data = cart_payload(db, cart)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao fundir carrinho no login")
        cart_data = dict(EMPTY_CART)
    return {"user": user.as_dict(), "access_token": token, "token_type": "bearer", "cart": cart_data}


@app.post("/api/auth/logout")
def api_logout(response: Response):
    auth.clear_auth_cookie(response)
    return {"ok": True, "detail": "Sessão encerrada"}


@app.get("/api/auth/me")
def api_me(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = auth.require_user(request, db)
    return user.as_dict()


# ===========================================================================
# API — CATÁLOGO
# ===========================================================================
@app.get("/api/categories")
def api_categories(db: Annotated[Session, Depends(get_db)]):
    return categories_payload(db)


@app.get("/api/products")
def api_products(
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    sort: str = "relevance",
    on_sale: str | None = None,
    in_stock: str | None = None,
):
    categoria = find_category(db, category)
    if category and categoria is None:
        return {"total": 0, "page": 1, "limit": limit, "pages": 1, "items": []}
    return query_products(
        db,
        q=q,
        category=categoria,
        page=page,
        limit=limit,
        sort=sort,
        on_sale=_flag(on_sale),
        in_stock=_flag(in_stock),
    )


@app.get("/api/products/{slug_or_id}")
def api_product(slug_or_id: str, db: Annotated[Session, Depends(get_db)]):
    product = find_product(db, slug_or_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product.as_dict(full=True)


# ===========================================================================
# API — CARRINHO
# ===========================================================================
def _cart_response(request: Request, response: Response, db: Session, user: User | None) -> dict:
    cart = resolve_cart(db, request, user)
    apply_cart_cookie(response, cart)
    return cart_payload(db, cart)


@app.get("/api/cart")
def api_cart_get(request: Request, response: Response, db: Annotated[Session, Depends(get_db)]):
    return _cart_response(request, response, db, auth.optional_user(request, db))


@app.post("/api/cart/items")
def api_cart_add(
    payload: CartItemIn,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    user = auth.optional_user(request, db)
    product = db.get(Product, payload.product_id)
    if product is None or not product.active:
        product = find_product(db, payload.product_id)
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    cart = resolve_cart(db, request, user)
    max_qty = max(1, int(product.max_qty or 999))
    qty = max(1, min(payload.qty, max_qty))
    item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
    )
    if item is None:
        db.add(CartItem(cart_id=cart.id, product_id=product.id, qty=qty))
    else:
        item.qty = max(1, min(item.qty + qty, max_qty))
    cart.updated_at = utcnow()
    db.commit()
    apply_cart_cookie(response, cart)
    return cart_payload(db, cart)


@app.patch("/api/cart/items/{product_id}")
def api_cart_update(
    product_id: str,
    payload: CartQtyIn,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    user = auth.optional_user(request, db)
    cart = resolve_cart(db, request, user)
    item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item não está no carrinho")
    if payload.qty <= 0:
        db.delete(item)
    else:
        product = db.get(Product, product_id)
        max_qty = max(1, int(product.max_qty or 999)) if product else 999
        item.qty = max(1, min(payload.qty, max_qty))
    cart.updated_at = utcnow()
    db.commit()
    apply_cart_cookie(response, cart)
    return cart_payload(db, cart)


@app.delete("/api/cart/items/{product_id}")
def api_cart_remove(
    product_id: str,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    user = auth.optional_user(request, db)
    cart = resolve_cart(db, request, user)
    item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    )
    if item is not None:
        db.delete(item)
        cart.updated_at = utcnow()
        db.commit()
    apply_cart_cookie(response, cart)
    return cart_payload(db, cart)


@app.post("/api/cart/merge")
def api_cart_merge(request: Request, response: Response, db: Annotated[Session, Depends(get_db)]):
    user = auth.require_user(request, db)
    cart = merge_carts(db, request_cart_token(request), user)
    apply_cart_cookie(response, cart)
    return cart_payload(db, cart)


@app.delete("/api/cart")
def api_cart_clear(request: Request, response: Response, db: Annotated[Session, Depends(get_db)]):
    user = auth.optional_user(request, db)
    cart = resolve_cart(db, request, user)
    cart.items.clear()
    cart.updated_at = utcnow()
    db.commit()
    apply_cart_cookie(response, cart)
    return cart_payload(db, cart)


# ===========================================================================
# API — PEDIDOS
# ===========================================================================
@app.post("/api/checkout", status_code=status.HTTP_201_CREATED)
def api_checkout(
    payload: CheckoutIn,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    user = auth.require_user(request, db)
    cart = resolve_cart(db, request, user)
    if not cart.items:
        cart = merge_carts(db, request_cart_token(request), user)

    rows = db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    ).all()
    if not rows:
        raise HTTPException(status_code=400, detail="Seu carrinho está vazio")

    ship = payload.ship or ShipIn()
    ship_name = (ship.name or "").strip() or user.name
    ship_cep = re.sub(r"\D", "", ship.cep or "")
    if not ship_name or not ship_cep:
        raise HTTPException(
            status_code=422,
            detail="Informe o nome do destinatário e o CEP para concluir o pedido",
        )

    subtotal = Decimal("0.00")
    order_items: list[OrderItem] = []
    for cart_item, product in rows:
        price = unit_price(product)
        line = money(price * cart_item.qty)
        subtotal += line
        order_items.append(
            OrderItem(
                product_id=product.id,
                name=product.name,
                unit_price=price,
                qty=cart_item.qty,
                subtotal=line,
            )
        )
    subtotal = money(subtotal)
    shipping = Decimal("0.00")  # frete calculado no servidor (grátis nesta versão)
    total = money(subtotal + shipping)

    order = Order(
        user_id=user.id,
        status="pendente",
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        payment=payload.payment,
        ship_name=ship_name,
        ship_email=(ship.email or user.email),
        ship_phone=ship.phone or user.phone,
        ship_cep=ship_cep,
        ship_address=ship.address,
        ship_number=ship.number,
        ship_complement=ship.complement,
        ship_district=ship.district,
        ship_city=ship.city,
        ship_state=(ship.state or "").upper() or None,
        items=order_items,
    )
    db.add(order)
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    cart.updated_at = utcnow()
    db.commit()
    db.refresh(order)
    apply_cart_cookie(response, cart)
    logger.info("Pedido %s criado (usuário %s) total=%.2f", order.id, user.id, float(total))
    return {"order": order_payload(order)}


@app.get("/api/orders")
def api_orders(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = auth.require_user(request, db)
    orders = list(
        db.scalars(
            select(Order)
            .where(Order.user_id == user.id)
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
    )
    return {"orders": [order_payload(o) for o in orders], "total": len(orders)}


@app.get("/api/orders/{order_id}")
def api_order(order_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    user = auth.require_user(request, db)
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="Você não tem acesso a este pedido")
    return order_payload(order)


# ===========================================================================
# Extras / tratamento de erro
# ===========================================================================
@app.get("/api/health")
def api_health(db: Annotated[Session, Depends(get_db)]):
    """Healthcheck (usado pelo Vercel): status + backend escolhido + nº de produtos.

    ``db`` é o rótulo seguro ("sqlite:<path>" ou "postgres:<host>/<banco>"),
    nunca a URL com senha.
    """
    products = int(db.scalar(select(func.count(Product.id))) or 0)
    categories = int(db.scalar(select(func.count(Category.id))) or 0)
    return {
        "status": "ok",
        "db": backend_label(),
        "products": products,
        "ok": True,  # alias legado
        "categories": categories,
        "templates": TEMPLATES_DIR.exists(),
    }


def _render_404(request: Request) -> HTMLResponse:
    db = SessionLocal()
    try:
        user = auth.optional_user(request, db)
        return render(
            request,
            "404.html",
            db=db,
            user=user,
            status_code=404,
            page_title=f"Página não encontrada | {STORE_NAME}",
        )
    finally:
        db.close()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    path = request.url.path
    if path == "/api" or path.startswith("/api/"):
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers or None
        )
    if exc.status_code == 404:
        return _render_404(request)
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query"))
        errors.append(f"{loc}: {err.get('msg', 'valor inválido')}" if loc else err.get("msg", "valor inválido"))
    detail = "Dados inválidos — " + "; ".join(errors[:5])
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": detail, "errors": exc.errors()}, status_code=422)
    return PlainTextResponse(detail, status_code=422)


if __name__ == "__main__":  # pragma: no cover - atalho para desenvolvimento
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8099, reload=True)

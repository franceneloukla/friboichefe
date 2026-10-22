"""Modelos ORM (SQLAlchemy 2.0, estilo DeclarativeBase/Mapped) — schema do CONTRATO."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:  # pacote (python -m server.app)
    from .db import Base
except ImportError:  # módulo solto (uvicorn app:app dentro de server/)
    from db import Base  # type: ignore[no-redef]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(190), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str | None] = mapped_column(String(14))
    phone: Mapped[str | None] = mapped_column(String(30))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    carts: Mapped[list["Cart"]] = relationship(back_populates="user")
    orders: Mapped[list["Order"]] = relationship(back_populates="user")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "cpf": self.cpf,
            "phone": self.phone,
            "is_admin": bool(self.is_admin),
        }


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "parent_id": self.parent_id,
            "sort": self.sort,
        }


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    sku: Mapped[str | None] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), index=True)
    category_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(10), default="KG", nullable=False)
    ean: Mapped[str | None] = mapped_column(String(40))
    weight_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    weight_avg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    weight_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    stock: Mapped[str] = mapped_column(String(40), default="Indisponível", nullable=False)
    max_qty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    search_blob: Mapped[str | None] = mapped_column(Text, index=True)
    description_html: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(255))
    # search_blob: name+brand+sku+ean minúsculos e sem acento (preenchido pelo seed)
    attrs_json: Mapped[str | None] = mapped_column(Text)
    nutrition_json: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    def as_dict(self, full: bool = False) -> dict:
        """Serialização usada pela API e pelos templates (sempre em float)."""
        return product_to_dict(self, full=full)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User | None"] = relationship(back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartItem.id",
        passive_deletes=True,
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="pendente", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    shipping: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    payment: Mapped[str | None] = mapped_column(String(20))
    ship_name: Mapped[str | None] = mapped_column(String(120))
    ship_email: Mapped[str | None] = mapped_column(String(190))
    ship_phone: Mapped[str | None] = mapped_column(String(30))
    ship_cep: Mapped[str | None] = mapped_column(String(12))
    ship_address: Mapped[str | None] = mapped_column(String(190))
    ship_number: Mapped[str | None] = mapped_column(String(20))
    ship_complement: Mapped[str | None] = mapped_column(String(120))
    ship_district: Mapped[str | None] = mapped_column(String(120))
    ship_city: Mapped[str | None] = mapped_column(String(120))
    ship_state: Mapped[str | None] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
        passive_deletes=True,
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


# ---------------------------------------------------------------------------
# Helpers de serialização (usados por app.py e seed.py)
# ---------------------------------------------------------------------------
def _money(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _num(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def json_load(raw: str | None, default):
    """json.loads tolerante: nunca derruba a request por causa de JSON inválido."""
    import json

    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def image_url(image_path: str | None) -> str | None:
    """``products/123/main.jpg`` -> ``/img/products/123/main.jpg``."""
    if not image_path:
        return None
    rel = image_path.lstrip("/")
    for prefix in ("data/images/", "images/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
    if rel.startswith("products/"):
        rel = rel[len("products/"):]
    return f"/img/products/{rel}"


def product_to_dict(product: Product, full: bool = False) -> dict:
    price = _money(product.price) or 0.0
    sale_price = _money(product.sale_price)
    data = {
        "id": product.id,
        "sku": product.sku or product.id,
        "name": product.name,
        "slug": product.slug,
        "brand": product.brand,
        "category_id": product.category_id,
        "price": price,
        "sale_price": sale_price,
        "effective_price": sale_price if sale_price is not None else price,
        "on_sale": sale_price is not None and sale_price < price,
        "discount_percent": (
            round((1 - sale_price / price) * 100) if sale_price and price and sale_price < price else 0
        ),
        "unit": product.unit,
        "weight_min": _num(product.weight_min),
        "weight_avg": _num(product.weight_avg),
        "weight_max": _num(product.weight_max),
        "stock": product.stock,
        "in_stock": (product.stock or "").strip().lower().startswith("dispon"),
        "max_qty": product.max_qty,
        "image_url": image_url(product.image_path),
        "image_path": product.image_path,
        "attrs": json_load(product.attrs_json, {}),
        "active": bool(product.active),
    }
    if full:
        data.update(
            {
                "ean": product.ean,
                "description_html": product.description_html or "",
                "video_url": product.video_url,
                "nutrition": json_load(product.nutrition_json, []),
                "images": [u for u in [image_url(product.image_path)] if u],
            }
        )
    return data

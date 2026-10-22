"""Normalização de texto compartilhada (app, seed e build do banco).

Módulo isolado de propósito: ``app.py`` e ``seed.py`` importam daqui a MESMA
normalização, sem criar import circular (app -> seed).

``fold_text`` deixa o texto minúsculo e sem acento usando NFKD (cobre qualquer
caractere latino acentuado), então ``"ACÉM"``, ``"acém"`` e ``"acem"`` viram
todos ``"acem"``.

A busca do site não usa mais funções SQL gigantes (``REPLACE`` aninhado): a
coluna ``products.search_blob`` guarda ``name + brand + sku + ean`` já
normalizados e a query faz um único ``LIKE``.
"""

from __future__ import annotations

import unicodedata


def fold_text(value: str | None) -> str:
    """Minúsculas e sem acento: ``"ACÉM Picanha"`` -> ``"acem picanha"``."""
    text = (value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def make_search_blob(*parts: str | None) -> str:
    """Monta o texto de busca do produto (campos normalizados, separados por espaço)."""
    return " ".join(part for part in (fold_text(p) for p in parts if p) if part)

"""Entrypoint serverless (Vercel).

O Vercel entrega a requisição já reescrita para a função (o rewrite aponta para
`/api/index/$1`), então o path que o ASGI enxerga pode vir como
`/api/index/login` em vez de `/login`. Este módulo instala um middleware que
devolve ao `scope` o caminho real antes do roteamento do FastAPI.

Também aceita o caminho original vindo por header (caso a plataforma opte por
preservá-lo), então funciona nos dois modos de roteamento do Vercel.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app import app  # noqa: E402

FUNCTION_PREFIX = "/api/index"
ORIGINAL_PATH_HEADERS = (
    b"x-vercel-original-path",
    b"x-forwarded-uri",
    b"x-original-url",
    b"x-invoke-path",
    b"x-rewrite-url",
)


def _restore_path(scope: dict) -> str:
    """Devolve o caminho real a partir do path reescrito ou de um header."""
    path = scope.get("path") or "/"
    headers = dict(scope.get("headers") or [])

    for name in ORIGINAL_PATH_HEADERS:
        value = headers.get(name)
        if value:
            try:
                candidate = value.decode("latin-1")
            except Exception:  # pragma: no cover - header inválido
                continue
            if candidate.startswith("/"):
                return candidate

    if path == FUNCTION_PREFIX:
        return "/"
    if path.startswith(FUNCTION_PREFIX + "/"):
        rest = path[len(FUNCTION_PREFIX):]
        return rest or "/"
    return path


class FixVercelPath:
    """ASGI middleware que restaura o caminho antes do roteamento."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket"):
            real = _restore_path(scope)
            if real != scope.get("path"):
                scope = {**scope, "path": real, "raw_path": real.encode("latin-1")}
        await self.app(scope, receive, send)


app.add_middleware(FixVercelPath)

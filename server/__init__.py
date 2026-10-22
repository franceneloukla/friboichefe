"""Pacote do backend da loja (FastAPI + SQLAlchemy).

Existe como pacote explícito (e não namespace) para que o empacotador de
funções do Vercel e o rastreio de imports enxerguem `server.app` de forma
determinística.
"""

__all__ = ["app"]

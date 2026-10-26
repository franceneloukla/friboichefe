"""Unidades Federativas do Brasil — fonte única de verdade (27 UFs).

Usado por três consumidores:

- ``GET /api/cotacao/ufs`` (payload ``[{sigla, nome}]`` em ordem alfabética);
- o formulário ``/cotacao`` (contexto ``ufs``);
- a validação de ``POST /api/cotacao``.

Módulo sem dependência do app (só do ``textutil``) para poder ser importado tanto
como pacote (``python -m server.app``) quanto solto (``uvicorn app:app`` de dentro
de ``server/``).

A normalização aceita a sigla (``"sp"``) ou o nome por extenso (``"São Paulo"``,
``"sao paulo"``, ``"SAO PAULO"``) e devolve sempre a sigla em maiúsculas — o
formulário manda sigla, integrações costumam mandar o nome.
"""

from __future__ import annotations

try:  # pacote (python -m server.app)
    from .textutil import fold_text
except ImportError:  # módulo solto (uvicorn app:app dentro de server/)
    from textutil import fold_text  # type: ignore[no-redef]

# Ordem alfabética pela sigla (a convenção usada em todo o site).
UFS: tuple[tuple[str, str], ...] = (
    ("AC", "Acre"),
    ("AL", "Alagoas"),
    ("AM", "Amazonas"),
    ("AP", "Amapá"),
    ("BA", "Bahia"),
    ("CE", "Ceará"),
    ("DF", "Distrito Federal"),
    ("ES", "Espírito Santo"),
    ("GO", "Goiás"),
    ("MA", "Maranhão"),
    ("MG", "Minas Gerais"),
    ("MS", "Mato Grosso do Sul"),
    ("MT", "Mato Grosso"),
    ("PA", "Pará"),
    ("PB", "Paraíba"),
    ("PE", "Pernambuco"),
    ("PI", "Piauí"),
    ("PR", "Paraná"),
    ("RJ", "Rio de Janeiro"),
    ("RN", "Rio Grande do Norte"),
    ("RO", "Rondônia"),
    ("RR", "Roraima"),
    ("RS", "Rio Grande do Sul"),
    ("SC", "Santa Catarina"),
    ("SE", "Sergipe"),
    ("SP", "São Paulo"),
    ("TO", "Tocantins"),
)

#: Sigla -> nome por extenso.
UF_NOMES: dict[str, str] = dict(UFS)

#: Todas as siglas válidas (27).
UF_SIGLAS: tuple[str, ...] = tuple(sigla for sigla, _nome in UFS)

#: Nome por extenso sem acento/minúsculo -> sigla.
UF_POR_NOME: dict[str, str] = {fold_text(nome): sigla for sigla, nome in UFS}

#: Total esperado de UFs (usado em testes e no contrato).
TOTAL_UFS = 27


def normalizar_uf(valor: str | None) -> str | None:
    """Normaliza uma UF para a sigla de 2 letras, ou ``None`` se não existir.

    - ``"sp"``, ``"SP"``, ``" Sp "`` -> ``"SP"``
    - ``"São Paulo"``, ``"sao paulo"`` -> ``"SP"``
    - ``"XX"``, ``""``, ``None`` -> ``None``
    """
    if not valor:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    sigla = texto.upper()
    if len(sigla) == 2:
        return sigla if sigla in UF_NOMES else None
    return UF_POR_NOME.get(fold_text(texto))


def nome_uf(sigla: str | None) -> str | None:
    """Sigla -> nome por extenso (``"SP"`` -> ``"São Paulo"``)."""
    if not sigla:
        return None
    return UF_NOMES.get(str(sigla).strip().upper())


def ufs_payload() -> list[dict]:
    """Lista pronta para o JSON/formulário: ``[{sigla, nome}]`` (27, alfabética)."""
    return [{"sigla": sigla, "nome": nome} for sigla, nome in UFS]


def ufs_siglas() -> list[str]:
    """Só as siglas, na mesma ordem (27)."""
    return list(UF_SIGLAS)


__all__ = [
    "TOTAL_UFS",
    "UFS",
    "UF_NOMES",
    "UF_POR_NOME",
    "UF_SIGLAS",
    "nome_uf",
    "normalizar_uf",
    "ufs_payload",
    "ufs_siglas",
]

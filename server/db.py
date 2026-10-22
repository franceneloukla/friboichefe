"""Camada de banco — DB-agnóstica (SQLite local / Postgres serverless) com SQLAlchemy 2.0.

Resolução do engine, em ordem:

1. ``DATABASE_URL`` definida e não vazia:
   - ``postgres://...`` é convertida para ``postgresql+psycopg2://...`` (formato do Heroku/Vercel);
   - ``pool_pre_ping=True`` e ``pool_recycle=280`` (protege contra conexão morta em serverless).
2. Sem ``DATABASE_URL``: SQLite em ``data/store.db`` (default local), com
   ``check_same_thread=False`` e ``PRAGMA foreign_keys=ON`` em toda conexão.

``init_db(seed_if_empty=True)`` cria as tabelas e, se a tabela ``products`` estiver vazia
E existir um catálogo (``CATALOG_PATH`` ou ``data/catalog.json``), roda o seed sozinho —
é isso que faz o primeiro cold start no Vercel funcionar.

Todos os caminhos saem de ``Path(__file__).resolve().parent.parent`` (raiz do projeto):
nunca de cwd, nunca de caminho absoluto de máquina.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger("friboi.db")

# ---------------------------------------------------------------------------
# Caminhos (sempre derivados do próprio arquivo, nunca do CWD)
# ---------------------------------------------------------------------------
SERVER_DIR: Path = Path(__file__).resolve().parent
ROOT_DIR: Path = SERVER_DIR.parent
DATA_DIR: Path = Path(os.environ.get("DATA_DIR") or (ROOT_DIR / "data")).expanduser()
CATALOG_PATH: Path = Path(
    os.environ.get("CATALOG_PATH") or (ROOT_DIR / "data" / "catalog.json")
).expanduser()

# SQLite efêmero usado quando o filesystem é somente leitura (Vercel sem DATABASE_URL)
TMP_DB_PATH: Path = Path(tempfile.gettempdir()) / "friboi-store.db"


def dir_is_writable(path: Path) -> bool:
    """Testa escrita real (mkdir existente + probe), não só permissão nominal."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write-probe-{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def resolve_sqlite_path() -> Path:
    """Regra do deploy:

    - ``DB_PATH`` explícito manda, desde que o diretório seja gravável;
    - no Vercel (env ``VERCEL``) ou com ``DATA_DIR`` somente leitura, o SQLite vai
      para o tempdir (funciona, mas é efêmero: cada cold start re-seeda);
    - caso contrário, SQLite persistente em ``data/store.db``.
    """
    explicit = (os.environ.get("DB_PATH") or "").strip()
    if explicit:
        candidate = Path(explicit).expanduser()
        if dir_is_writable(candidate.parent):
            return candidate
        return TMP_DB_PATH
    if os.environ.get("VERCEL") or not dir_is_writable(DATA_DIR):
        return TMP_DB_PATH
    return (DATA_DIR / "store.db").expanduser()


DB_PATH: Path = resolve_sqlite_path()


def normalize_database_url(raw: str | None) -> str:
    """Normaliza a URL: ``postgres://`` -> ``postgresql+psycopg2://`` (formato Heroku/Vercel)."""
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("postgres://"):
        return "postgresql+psycopg2://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg2://" + value[len("postgresql://"):]
    return value


def _env_url() -> str:
    return normalize_database_url(os.environ.get("DATABASE_URL"))


DATABASE_URL: str = _env_url()
IS_POSTGRES: bool = DATABASE_URL.startswith("postgresql")
IS_SQLITE: bool = not DATABASE_URL


def _create_engine() -> Engine:
    if DATABASE_URL:
        try:
            return create_engine(
                DATABASE_URL,
                echo=bool(int(os.environ.get("SQL_ECHO", "0") or 0)),
                future=True,
                pool_pre_ping=True,
                pool_recycle=280,
            )
        except ModuleNotFoundError as exc:  # driver ausente
            raise RuntimeError(
                "DATABASE_URL aponta para Postgres, mas o driver psycopg2 não está instalado. "
                "Instale 'psycopg2-binary' (ou use psycopg[binary] e ajuste a URL)."
            ) from exc

    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # filesystem somente leitura (ex.: serverless sem DATABASE_URL)
        logger.warning("Não foi possível criar %s (%s); o SQLite pode falhar.", DB_PATH.parent, exc)
    sqlite_engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=bool(int(os.environ.get("SQL_ECHO", "0") or 0)),
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(sqlite_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()

    return sqlite_engine


engine: Engine = _create_engine()

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def backend_label_from_url(url: str | None) -> str:
    """Rótulo seguro do backend: ``sqlite:<path>`` ou ``postgres:<host>/<banco>``.

    Nunca inclui usuário/senha da URL.
    """
    if not url:
        return f"sqlite:{DB_PATH}"
    try:
        parsed = make_url(url)
    except Exception:  # noqa: BLE001 - URL malformada não pode vazar credenciais
        return "postgres:?"
    host = parsed.host or "?"
    database = (parsed.database or "").strip("/") or "?"
    return f"postgres:{host}/{database}"


def backend_label() -> str:
    """Backend efetivamente escolhido (sem segredo) — usado no log e no /api/health."""
    return backend_label_from_url(DATABASE_URL)


_backend_logged = False


def log_backend() -> str:
    """Loga UMA linha por processo com o backend escolhido."""
    global _backend_logged
    label = backend_label()
    if not _backend_logged:
        _backend_logged = True
        logger.info("Banco: %s", label)
    return label


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos."""


def get_db() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por request, fechada no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def _load_models() -> None:
    """Importa os modelos nos dois modos de execução (pacote ou módulo solto)."""
    try:  # python -m server.app / from server.app import app
        from . import models  # noqa: F401
    except (ImportError, ValueError):  # uvicorn app:app rodando de dentro de server/
        import models  # noqa: F401


def catalog_path() -> Path:
    """Caminho do catálogo usado pelo auto-seed (respeita CATALOG_PATH)."""
    raw = (os.environ.get("CATALOG_PATH") or "").strip()
    return Path(raw).expanduser() if raw else (ROOT_DIR / "data" / "catalog.json")


def _products_count(db: Session) -> int:
    from sqlalchemy import text

    try:
        return int(db.execute(text("select count(*) from products")).scalar() or 0)
    except Exception:  # noqa: BLE001 - tabela ainda não existe
        return 0


_auto_seed_running = False


def init_db(seed_if_empty: bool = True) -> None:
    """Cria o schema e (opcionalmente) popula o banco se estiver vazio.

    Idempotente e seguro para chamar em todo boot/cold start:
    - ``create_all`` só cria o que falta;
    - o seed só roda se ``products`` estiver vazia e o catálogo existir;
    - erros de seed são logados, nunca derrubam a aplicação.
    """
    global _auto_seed_running
    log_backend()
    _load_models()
    Base.metadata.create_all(bind=engine)

    if not seed_if_empty or _auto_seed_running:
        return
    if (os.environ.get("SEED_ON_INIT", "1") or "1") != "1":
        return

    path = catalog_path()
    if not path.is_file():
        logger.warning("Auto-seed ignorado: catálogo ausente em %s", path)
        return

    db = SessionLocal()
    try:
        if _products_count(db) > 0:
            return
    finally:
        db.close()

    _auto_seed_running = True
    try:
        try:  # pacote
            from .seed import run_seed
        except ImportError:  # módulo solto
            from seed import run_seed  # type: ignore[no-redef]

        logger.info("Banco vazio: rodando seed automático de %s", path)
        stats = run_seed(path, verbose=False)
        logger.info("Seed automático concluído: %s", stats)
    except Exception:  # noqa: BLE001 - cold start nunca deve falhar por causa do seed
        logger.exception("Falha no seed automático (a aplicação continua no ar)")
    finally:
        _auto_seed_running = False


def reset_db() -> None:
    """Derruba e recria todas as tabelas (manutenção; não roda seed)."""
    _load_models()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

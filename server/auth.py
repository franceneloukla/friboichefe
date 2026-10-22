"""Autenticação: hash bcrypt (direto, sem passlib) + JWT HS256 (python-jose).

- Senha: ``bcrypt.hashpw`` / ``bcrypt.checkpw``.
- Token: JWT HS256, expira em 7 dias, entregue em cookie httpOnly ``auth_token``
  e também no corpo JSON (``access_token`) para clientes que prefiram ``Bearer``.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

try:  # pacote
    from .models import User
except ImportError:  # módulo solto
    from models import User  # type: ignore[no-redef]

SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-friboi-online-troque-em-producao")
ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("JWT_EXPIRE_DAYS", "7"))
ACCESS_TOKEN_EXPIRE_SECONDS: int = ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

COOKIE_NAME: str = "auth_token"
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "0") == "1"
COOKIE_SAMESITE: str = os.environ.get("COOKIE_SAMESITE", "lax")

# bcrypt só considera os primeiros 72 bytes da senha
BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro."""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Compara senha em texto puro com o hash guardado (nunca levanta exceção)."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user: User | int, email: str | None = None) -> str:
    """Monta o JWT do usuário com validade de 7 dias."""
    user_id = user if isinstance(user, int) else user.id
    user_email = email if email is not None else (user.email if not isinstance(user, int) else None)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": user_email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def token_from_request(request: Request) -> str | None:
    """Cookie httpOnly primeiro; ``Authorization: Bearer <token>`` como alternativa."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    return user if user and user.id else None


def optional_user(request: Request, db: Session) -> User | None:
    """Usuário logado ou ``None`` (nunca levanta 401)."""
    return user_from_token(db, token_from_request(request))


def require_user(request: Request, db: Session) -> User:
    """Dependência de rota: exige JWT válido, senão 401 em PT-BR."""
    user = optional_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado. Faça login para continuar.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def set_auth_cookie(response: Response, token: str) -> None:
    """Grava o JWT no cookie httpOnly ``auth_token``."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,  # type: ignore[arg-type]
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True, samesite=COOKIE_SAMESITE)  # type: ignore[arg-type]

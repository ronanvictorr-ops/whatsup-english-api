import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def is_production() -> bool:
    return (
        os.getenv("ENVIRONMENT", "development").strip().lower() == "production"
        or os.getenv("RENDER", "").strip().lower() == "true"
    )


def get_secret_key() -> str:
    configured = os.getenv("SECRET_KEY")
    if is_production() and (
        not configured or configured == "whatsup-english-secret-key"
    ):
        raise RuntimeError("SECRET_KEY segura e obrigatoria em producao")
    return configured or "whatsup-english-local-development-only"


def validate_security_configuration() -> None:
    get_secret_key()


def create_access_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[ALGORITHM],
        )
        if not payload.get("student_id"):
            raise JWTError("Token sem student_id")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido")


def require_dashboard_admin(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
):
    configured_key = os.getenv("DASHBOARD_ADMIN_TOKEN")
    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="DASHBOARD_ADMIN_TOKEN nao configurado",
        )
    if not x_admin_key or not secrets.compare_digest(x_admin_key, configured_key):
        raise HTTPException(status_code=401, detail="Chave administrativa invalida")
    return True


def require_student_access(student_id: int, current_user: dict) -> None:
    try:
        authenticated_student_id = int(current_user.get("student_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token sem aluno valido")
    if authenticated_student_id != int(student_id):
        raise HTTPException(status_code=403, detail="Acesso negado a este aluno")


def meta_signature_required() -> bool:
    return os.getenv(
        "META_SIGNATURE_REQUIRED",
        "true" if is_production() else "false",
    ).strip().lower() == "true"


def verify_meta_webhook_signature(payload: bytes, signature: str | None) -> None:
    if not meta_signature_required():
        return

    app_secret = os.getenv("META_APP_SECRET")
    if not app_secret:
        raise HTTPException(status_code=503, detail="META_APP_SECRET nao configurado")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Assinatura da Meta ausente")

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    if not secrets.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Assinatura da Meta invalida")

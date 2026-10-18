"""安全模块：JWT 签发校验、bcrypt 密码、Fernet 凭据加密。"""
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise AuthError("无效的登录凭证，请重新登录") from e


def _fernet() -> Fernet:
    return Fernet(settings.credential_secret.encode())


def encrypt_secret(plain: str) -> str:
    """凭据加密：返回 base64 字符串。若配置的密钥不是合法 Fernet key，用其 sha256 派生。"""
    try:
        return _fernet().encrypt(plain.encode()).decode()
    except Exception:
        import hashlib

        derived = base64.urlsafe_b64encode(hashlib.sha256(settings.credential_secret.encode()).digest())
        return Fernet(derived).encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> Optional[str]:
    if not cipher:
        return None
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except (InvalidToken, Exception):
        import hashlib

        derived = base64.urlsafe_b64encode(hashlib.sha256(settings.credential_secret.encode()).digest())
        try:
            return Fernet(derived).decrypt(cipher.encode()).decode()
        except InvalidToken:
            return None

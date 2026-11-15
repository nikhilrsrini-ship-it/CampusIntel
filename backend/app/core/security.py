import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import get_settings

ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, digest = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(digest))
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_access_token(user_id: UUID, role: str, token_version: int = 0) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": str(user_id), "role": role, "ver": token_version, "iat": now, "exp": now + get_settings().jwt_expire_minutes * 60}, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode()
    signature = _b64(hmac.new(get_settings().jwt_secret.encode(), message, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(get_settings().jwt_secret.encode(), message, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise unauthorized
        header_claims = json.loads(base64.urlsafe_b64decode(header + "=" * (-len(header) % 4)))
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if header_claims.get("alg") != "HS256" or int(claims.get("exp", 0)) <= int(time.time()):
            raise unauthorized
        UUID(claims["sub"])
        return claims
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise unauthorized

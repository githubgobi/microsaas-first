import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import anyio
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import JWT_ALGORITHM, get_settings

settings = get_settings()

# bcrypt__truncate_error=False: passlib silently truncates passwords >72 bytes
# rather than raising. Our schema validator rejects them before they reach here,
# so this is a belt-and-suspenders guard — it also prevents bcrypt>=4.0 from
# firing its own truncation error before passlib's logic runs.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

# Generated once at import time — valid bcrypt hash used as a timing guard in login
# when the email doesn't exist. Running the full KDF prevents user-enumeration via
# response-time differences. Never hardcode a literal hash string; passlib must
# generate it so the format is always valid for the active bcrypt variant.
DUMMY_HASH: str = _pwd_context.hash("timing-guard")


# --- Password (async wrappers — bcrypt is CPU-bound; must not block event loop) ---

async def hash_password(password: str) -> str:
    return await anyio.to_thread.run_sync(lambda: _pwd_context.hash(password))


async def verify_password(plain: str, hashed: str) -> bool:
    """Runs bcrypt in a thread to avoid blocking the event loop.

    Returns False (never raises) so callers always get a bool regardless of
    whether `hashed` is a valid bcrypt string. This matters for the dummy-hash
    path in login: a malformed hash would otherwise raise ValueError inside
    passlib and produce a 500 instead of the expected 401.
    """
    try:
        return await anyio.to_thread.run_sync(lambda: _pwd_context.verify(plain, hashed))
    except Exception:
        return False


# --- Access token (JWT) ---

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


# --- Refresh token (opaque, stored as SHA-256 hash) ---

def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store only the hash."""
    raw = secrets.token_urlsafe(32)
    return raw, _hash_token(raw)


def hash_refresh_token(raw: str) -> str:
    return _hash_token(raw)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

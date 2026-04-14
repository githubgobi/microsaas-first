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


# --- Email verification token ---

def create_verification_token(user_id: str) -> str:
    """Short-lived JWT used only for email verification.

    The `type` claim prevents this token from being accepted as an access token
    or any other token type (algorithm-confusion / cross-token misuse defence).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS
    )
    return jwt.encode(
        {"sub": user_id, "type": "email_verification", "exp": expire},
        settings.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_verification_token(token: str) -> str | None:
    """Returns the user_id string on success, None on any failure or type mismatch."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "email_verification":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# --- Password reset token ---
#
# The token is signed with SECRET_KEY + user.hashed_password.
# When the password changes, the hash changes, invalidating all previously
# issued reset tokens automatically — single-use with no database state.
#
# Decode flow: extract sub without verifying first (to look up the user and
# obtain their current hash), then do a full signature check.

def create_password_reset_token(user_id: str, hashed_password: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    secret = settings.SECRET_KEY + hashed_password
    return jwt.encode(
        {"sub": user_id, "type": "password_reset", "exp": expire},
        secret,
        algorithm=JWT_ALGORITHM,
    )


def _extract_reset_token_subject(token: str) -> str | None:
    """Return the sub claim without verifying the signature.

    Used only to look up the user so we can obtain their hashed_password
    and then perform a full signature check. Never trust this value alone.
    """
    try:
        claims = jwt.get_unverified_claims(token)
        if claims.get("type") != "password_reset":
            return None
        return claims.get("sub")
    except JWTError:
        return None


def decode_password_reset_token(token: str, hashed_password: str) -> str | None:
    """Full verification — signature, expiry, and type claim.

    Returns the user_id string on success, None on any failure.
    Must be called with the user's *current* hashed_password; if the
    password has already been reset, the signature will not match.
    """
    try:
        secret = settings.SECRET_KEY + hashed_password
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "password_reset":
            return None
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

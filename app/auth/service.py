import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import RefreshTokenRepository, UserRepository
from app.auth.schemas import LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse
from app.auth.utils import (
    DUMMY_HASH as _DUMMY_HASH,
    _extract_reset_token_subject,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    decode_password_reset_token,
    decode_verification_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import get_settings
from app.core.email import send_password_reset_email, send_verification_email
from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError

logger = structlog.get_logger()

settings = get_settings()

# Single message for all login failures — never reveal which part failed
_INVALID_CREDENTIALS = "Invalid credentials"


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        try:
            user = await self.users.create(
                email=data.email,
                hashed_password=await hash_password(data.password),
            )
            token_response = await self._issue_tokens(user.id)
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Email already registered")

        # Send after commit — don't fail registration if the mail server is down.
        verification_token = create_verification_token(str(user.id))
        try:
            await send_verification_email(user.email, verification_token)
        except Exception:
            logger.warning("verification_email_failed", email=user.email, exc_info=True)

        return token_response

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_email(data.email)

        # Always run verify_password even when user doesn't exist to prevent
        # timing-based user enumeration attacks.
        #
        # The dummy hash MUST be a syntactically valid bcrypt string so passlib
        # runs the full KDF (~300 ms), not a fast path that leaks whether the
        # email exists via response-time difference.
        # Generated with: passlib.CryptContext(["bcrypt"]).hash("timing-guard")
        password_ok = await verify_password(
            data.password,
            user.hashed_password if user else _DUMMY_HASH,
        )

        if not user or not password_ok or not user.is_active:
            raise UnauthorizedError(_INVALID_CREDENTIALS)

        return await self._issue_tokens(user.id)

    async def refresh(self, raw_token: str) -> TokenResponse:
        token = await self.tokens.get_valid_by_hash(hash_refresh_token(raw_token))
        if not token:
            raise UnauthorizedError("Invalid or expired refresh token")

        await self.tokens.revoke(token)  # rotate: old token is invalidated
        return await self._issue_tokens(token.user_id)

    async def logout(self, raw_token: str) -> None:
        token = await self.tokens.get_valid_by_hash(hash_refresh_token(raw_token))
        if token:
            await self.tokens.revoke(token)
        await self.db.commit()

    async def verify_email(self, token: str) -> None:
        user_id_str = decode_verification_token(token)
        if not user_id_str:
            raise BadRequestError("Invalid or expired verification token")

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise BadRequestError("Invalid or expired verification token")

        user = await self.users.get_by_id(user_id)
        if not user:
            raise BadRequestError("Invalid or expired verification token")

        if not user.is_verified:
            await self.users.set_verified(user_id)
            await self.db.commit()

    async def resend_verification(self, email: str) -> None:
        """Always returns silently — never leaks whether the email exists."""
        user = await self.users.get_by_email(email)
        if not user or user.is_verified:
            return

        verification_token = create_verification_token(str(user.id))
        try:
            await send_verification_email(user.email, verification_token)
        except Exception:
            logger.warning("verification_email_failed", email=user.email, exc_info=True)

    async def forgot_password(self, email: str) -> None:
        """Always returns silently — never leaks whether the email exists."""
        user = await self.users.get_by_email(email)
        if not user or not user.is_active:
            return

        reset_token = create_password_reset_token(str(user.id), user.hashed_password)
        try:
            await send_password_reset_email(user.email, reset_token)
        except Exception:
            logger.warning("password_reset_email_failed", email=user.email, exc_info=True)

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        # Step 1 — extract user_id without trusting the signature yet
        user_id_str = _extract_reset_token_subject(data.token)
        if not user_id_str:
            raise BadRequestError("Invalid or expired reset token")

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise BadRequestError("Invalid or expired reset token")

        # Step 2 — fetch user so we have their current hashed_password
        user = await self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise BadRequestError("Invalid or expired reset token")

        # Step 3 — full signature + expiry check using current password hash as secret
        if not decode_password_reset_token(data.token, user.hashed_password):
            raise BadRequestError("Invalid or expired reset token")

        # Step 4 — update password and force logout from all devices
        new_hash = await hash_password(data.new_password)
        await self.users.update_password(user_id, new_hash)
        await self.tokens.revoke_all_for_user(user_id)
        await self.db.commit()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _issue_tokens(self, user_id: uuid.UUID) -> TokenResponse:
        access_token = create_access_token(str(user_id))
        raw_refresh, hashed_refresh = create_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.tokens.create(user_id, hashed_refresh, expires_at)
        await self.db.commit()

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh)

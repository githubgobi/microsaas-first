import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import RefreshTokenRepository, UserRepository
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError

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
            return await self._issue_tokens(user.id)
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Email already registered")

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_email(data.email)

        # Always run verify_password even when user doesn't exist to prevent
        # timing-based user enumeration attacks
        dummy_hash = "$2b$12$eImiTXuWVxfM37uY4JANjQ"  # placeholder for constant time
        password_ok = await verify_password(
            data.password,
            user.hashed_password if user else dummy_hash,
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

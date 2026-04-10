import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.utils import decode_access_token
from app.database import get_db

_bearer = HTTPBearer()
_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},  # required by RFC 7235
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id_str = decode_access_token(credentials.credentials)
    if not user_id_str:
        raise _401

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise _401  # malformed sub claim — treat as invalid token, not a 500

    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise _401

    return user

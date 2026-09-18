import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies import DbSession
from app.core.errors import AuthenticationError
from app.core.security import decode_access_token
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]


def get_auth_service(db: DbSession, users: UserRepo) -> AuthService:
    """Dependencies are injected, so a test can supply a fake repository."""
    return AuthService(db, users)


AuthSvc = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(
    users: UserRepo,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the caller from the bearer token, or reject the request."""
    if credentials is None:
        raise AuthenticationError("Not authenticated.")

    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise AuthenticationError("Invalid or expired token.")

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise AuthenticationError("Invalid token subject.") from None

    user = users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is unavailable.")
    from app.core.logging import user_id_var

    user_id_var.set(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

from fastapi import APIRouter, Request, status

from app.core.rate_limit import login_rate_limiter
from app.modules.auth.dependencies import AuthSvc, CurrentUser
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthSvc) -> TokenResponse:
    user = service.register(payload.email, payload.password, payload.full_name)
    return TokenResponse(access_token=service.issue_token(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, service: AuthSvc, request: Request) -> TokenResponse:
    # Throttled per email + client address so an attacker cannot grind
    # passwords, and cannot lock a victim out from a different address.
    key = f"{payload.email.lower()}|{request.client.host if request.client else 'unknown'}"
    login_rate_limiter.check(key)
    try:
        user = service.authenticate(payload.email, payload.password)
    except Exception:
        login_rate_limiter.record_failure(key)
        raise
    login_rate_limiter.reset(key)
    return TokenResponse(access_token=service.issue_token(user))


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> User:
    return current_user

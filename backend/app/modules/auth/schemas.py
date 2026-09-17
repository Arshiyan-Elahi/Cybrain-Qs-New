import uuid

from pydantic import EmailStr, Field, TypeAdapter, field_validator

from app.shared.schemas import CamelModel


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(CamelModel):
    # The repeatable local CKM fixture intentionally uses a reserved domain.
    # All normal accounts still receive the same EmailStr validation.
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_login_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "demo@cybrain.local":
            return normalized
        return str(TypeAdapter(EmailStr).validate_python(normalized))


class TokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(CamelModel):

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool

    @field_validator("email")
    @classmethod
    def validate_user_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "demo@cybrain.local":
            return normalized
        return str(TypeAdapter(EmailStr).validate_python(normalized))

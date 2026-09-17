from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository


class AuthService:
    def __init__(self, db: Session, users: UserRepository) -> None:
        self.db = db
        self.users = users

    def register(self, email: str, password: str, full_name: str) -> User:
        if self.users.get_by_email(email):
            raise ConflictError("An account with that email already exists.")
        user = self.users.create(email, hash_password(password), full_name)
        self.db.flush()
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email)
        # Same message either way so the endpoint cannot be used to enumerate accounts.
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))

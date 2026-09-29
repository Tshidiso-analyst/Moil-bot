from datetime import datetime, timedelta, timezone

from auth.models import Session, User
from auth.repository import UserRepository
from auth.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class RegistrationError(Exception):
    """Raised when registration validation fails."""


class AuthService:
    """Application service for Moil Bot registration and authentication."""

    SESSION_DURATION_HOURS = 24

    def __init__(self, repository: UserRepository | None = None):
        self.repository = repository or UserRepository()

    def register(
        self,
        full_name: str,
        username: str,
        email: str,
        password: str,
    ) -> User:
        full_name = full_name.strip()
        username = username.strip()
        email = email.strip().lower()

        self._validate_registration(
            full_name,
            username,
            email,
            password,
        )

        existing_user = self.repository.find_by_username_or_email(username)

        if existing_user is not None:
            raise RegistrationError("Username or email is already registered.")

        existing_email = self.repository.find_by_username_or_email(email)

        if existing_email is not None:
            raise RegistrationError("Username or email is already registered.")

        password_hash = hash_password(password)

        return self.repository.create_user(
            full_name=full_name,
            username=username,
            email=email,
            password_hash=password_hash,
        )

    def login(
        self,
        identifier: str,
        password: str,
    ) -> tuple[User, str, Session]:
        identifier = identifier.strip()

        user = self.repository.find_by_username_or_email(identifier)

        if user is None:
            raise AuthenticationError("Invalid username/email or password.")

        if not user.is_active:
            raise AuthenticationError("This account is inactive.")

        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid username/email or password.")

        raw_token = generate_token()
        token_hash = hash_token(raw_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.SESSION_DURATION_HOURS
        )

        session = self.repository.create_session(
            user_id=user.id,
            session_token_hash=token_hash,
            expires_at=expires_at,
        )

        return user, raw_token, session

    def authenticate_session(self, raw_token: str) -> User | None:
        if not raw_token:
            return None

        token_hash = hash_token(raw_token)
        session = self.repository.find_session(token_hash)

        if session is None:
            return None

        return self.repository.find_by_id(session.user_id)

    def logout(self, raw_token: str) -> None:
        if not raw_token:
            return

        token_hash = hash_token(raw_token)
        self.repository.delete_session(token_hash)

    @staticmethod
    def _validate_registration(
        full_name: str,
        username: str,
        email: str,
        password: str,
    ) -> None:
        if not full_name:
            raise RegistrationError("Full name is required.")

        if len(full_name) > 150:
            raise RegistrationError("Full name is too long.")

        if not username:
            raise RegistrationError("Username is required.")

        if len(username) < 3:
            raise RegistrationError(
                "Username must contain at least 3 characters."
            )

        if len(username) > 50:
            raise RegistrationError("Username is too long.")

        if not username.replace("_", "").isalnum():
            raise RegistrationError(
                "Username may contain only letters, numbers, and underscores."
            )

        if not email:
            raise RegistrationError("Email is required.")

        if len(email) > 191 or "@" not in email:
            raise RegistrationError("A valid email address is required.")

        if not password:
            raise RegistrationError("Password is required.")

        if len(password.encode("utf-8")) > 72:
            raise RegistrationError(
                "Password must be 72 bytes or fewer."
            )

        if len(password) < 8:
            raise RegistrationError(
                "Password must contain at least 8 characters."
            )

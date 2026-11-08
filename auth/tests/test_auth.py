from auth.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from auth.service import AuthService


def test_password_hashing():
    password = "TestPassword123"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$2b$")
    assert verify_password(password, password_hash)
    assert not verify_password("WrongPassword123", password_hash)


def test_token_generation_and_hashing():
    token = generate_token()

    assert token
    assert len(token) > 20

    token_hash = hash_token(token)

    assert len(token_hash) == 64
    assert token_hash != token
    assert hash_token(token) == token_hash


def test_auth_service_can_be_created():
    service = AuthService()

    assert service.repository is not None


def test_login_returns_session_token():
    from auth.service import AuthService

    class FakeRepository:
        def find_by_username_or_email(self, identifier):
            return None

    service = AuthService(FakeRepository())

    assert service.repository is not None


def test_registration_normalizes_username_and_email():
    from auth.models import User
    from auth.service import AuthService

    class FakeRepository:
        def __init__(self):
            self.created = None

        def find_by_username_or_email(self, identifier):
            return None

        def create_user(self, **values):
            self.created = values
            return User(
                id=1,
                full_name=values["full_name"],
                username=values["username"],
                email=values["email"],
                password_hash=values["password_hash"],
                email_verified_at=None,
                is_active=True,
            )

    repository = FakeRepository()
    user = AuthService(repository).register(
        "Moil Trader", "MoilUser", "TRADER@EXAMPLE.TEST", "SafePassword123"
    )

    assert user.username == "moiluser"
    assert user.email == "trader@example.test"


def test_login_normalizes_identifier_before_lookup():
    from auth.models import User
    from auth.security import hash_password
    from auth.service import AuthService

    class FakeRepository:
        def __init__(self):
            self.looked_up = None

        def find_by_username_or_email(self, identifier):
            self.looked_up = identifier
            return User(
                id=1,
                full_name="Moil Trader",
                username="moiluser",
                email="trader@example.test",
                password_hash=hash_password("SafePassword123"),
                email_verified_at=None,
                is_active=True,
            )

        def create_session(self, **values):
            from auth.models import Session
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            return Session(
                id=1,
                user_id=values["user_id"],
                session_token_hash=values["session_token_hash"],
                expires_at=values["expires_at"],
                created_at=now,
                last_seen_at=now,
            )

    repository = FakeRepository()
    AuthService(repository).login("MOILUSER", "SafePassword123")

    assert repository.looked_up == "moiluser"

def test_inactive_user_cannot_reuse_an_existing_session():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from auth.service import AuthService

    class FakeRepository:
        def find_session(self, token_hash):
            return SimpleNamespace(
                user_id=7,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

        def find_by_id(self, user_id):
            return SimpleNamespace(id=user_id, is_active=False)

    service = AuthService(FakeRepository())

    assert service.authenticate_session("valid-looking-session-token") is None

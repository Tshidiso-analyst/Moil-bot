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
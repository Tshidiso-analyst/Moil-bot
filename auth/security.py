import hashlib
import secrets

import bcrypt


def hash_password(password: str) -> str:
    """Hash a user password using bcrypt."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    if not password:
        raise ValueError("password cannot be empty")

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("password must be 72 bytes or fewer")

    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored bcrypt hash."""
    if not isinstance(password, str):
        return False

    if not isinstance(password_hash, str):
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def generate_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token before storing it in the database."""
    if not isinstance(token, str):
        raise TypeError("token must be a string")

    if not token:
        raise ValueError("token cannot be empty")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()

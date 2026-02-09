"""Password hashing service using Argon2id.

Thin wrappers around argon2-cffi for consistent password hashing
throughout the application.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: The plaintext password to hash.

    Returns:
        The Argon2id hash string.
    """
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against an Argon2id hash.

    Args:
        password_hash: The stored Argon2id hash.
        password: The plaintext password to verify.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check if a password hash needs to be rehashed.

    Args:
        password_hash: The stored Argon2id hash.

    Returns:
        True if the hash parameters are outdated and should be rehashed.
    """
    return _hasher.check_needs_rehash(password_hash)

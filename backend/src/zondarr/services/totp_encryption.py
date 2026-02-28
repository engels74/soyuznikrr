"""TOTP secret encryption using Fernet with HKDF-derived key.

Derives an encryption key from the application's secret_key using HKDF
(SHA-256) so the raw secret_key is never used directly as a Fernet key.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _derive_key(secret_key: str) -> bytes:
    """Derive a Fernet-compatible key from the application secret.

    Uses HKDF with SHA-256, a fixed salt and info context to produce
    a 32-byte key, then base64url-encodes it for Fernet.

    Args:
        secret_key: The application's secret key (min 32 chars).

    Returns:
        A base64url-encoded 32-byte key suitable for Fernet.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"zondarr-totp",
        info=b"totp-encryption",
    )
    raw_key = hkdf.derive(secret_key.encode())
    return base64.urlsafe_b64encode(raw_key)


def encrypt_totp_secret(plaintext: str, /, *, secret_key: str) -> str:
    """Encrypt a TOTP secret for database storage.

    Args:
        plaintext: The base32-encoded TOTP secret.
        secret_key: Application secret key used to derive the encryption key.

    Returns:
        The Fernet-encrypted ciphertext as a UTF-8 string.
    """
    fernet = Fernet(_derive_key(secret_key))
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_totp_secret(ciphertext: str, /, *, secret_key: str) -> str:
    """Decrypt a TOTP secret from database storage.

    Args:
        ciphertext: The Fernet-encrypted ciphertext string.
        secret_key: Application secret key used to derive the encryption key.

    Returns:
        The decrypted base32-encoded TOTP secret.

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data).
    """
    fernet = Fernet(_derive_key(secret_key))
    return fernet.decrypt(ciphertext.encode()).decode()


__all__ = ["InvalidToken", "decrypt_totp_secret", "encrypt_totp_secret"]

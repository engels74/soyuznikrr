"""TOTP two-factor authentication service.

Provides TOTP setup, verification, backup code generation, and QR code
rendering for admin accounts.
"""

import io
import secrets
import string

import msgspec
import pyotp
import segno
import structlog

from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount
from zondarr.services.password import hash_password, verify_password
from zondarr.services.totp_encryption import (
    InvalidToken,
    decrypt_totp_secret,
    encrypt_totp_secret,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# TOTP configuration
TOTP_ISSUER = "Zondarr"
TOTP_DIGITS = 6
TOTP_INTERVAL = 30

# Backup code configuration
BACKUP_CODE_COUNT = 10
BACKUP_CODE_CHARS = string.ascii_uppercase + string.digits
BACKUP_CODE_HALF_LEN = 4


def _generate_backup_code() -> str:
    """Generate a single backup code in XXXX-XXXX format.

    Returns:
        A random alphanumeric uppercase code like "A3B7-K9M2".
    """
    left = "".join(
        secrets.choice(BACKUP_CODE_CHARS) for _ in range(BACKUP_CODE_HALF_LEN)
    )
    right = "".join(
        secrets.choice(BACKUP_CODE_CHARS) for _ in range(BACKUP_CODE_HALF_LEN)
    )
    return f"{left}-{right}"


def generate_backup_codes() -> list[str]:
    """Generate a set of unique backup codes.

    Returns:
        A list of BACKUP_CODE_COUNT unique codes in XXXX-XXXX format.
    """
    codes: set[str] = set()
    while len(codes) < BACKUP_CODE_COUNT:
        codes.add(_generate_backup_code())
    return sorted(codes)


def hash_backup_codes(codes: list[str]) -> str:
    """Hash backup codes and serialize as JSON for storage.

    Each code is hashed with argon2 before storage so that the
    plaintext codes cannot be recovered from the database.

    Args:
        codes: List of plaintext backup codes.

    Returns:
        JSON string containing an array of argon2 hashes.
    """
    hashes = [hash_password(code) for code in codes]
    return msgspec.json.encode(hashes).decode()


def verify_backup_code(stored_hashes_json: str, code: str) -> tuple[bool, str | None]:
    """Verify a backup code against stored hashes.

    Checks the provided code against each stored hash. On match,
    returns the updated JSON with the used hash removed.

    Args:
        stored_hashes_json: JSON string of argon2 hashes.
        code: The backup code to verify.

    Returns:
        A tuple of (matched, updated_json). If matched is True,
        updated_json contains the remaining hashes. If False,
        updated_json is None.
    """
    hashes: list[str] = msgspec.json.decode(stored_hashes_json, type=list[str])
    normalized = code.upper().strip()

    for i, h in enumerate(hashes):
        if verify_password(h, normalized):
            remaining = hashes[:i] + hashes[i + 1 :]
            return True, msgspec.json.encode(remaining).decode()

    return False, None


class TOTPService:
    """Service for TOTP two-factor authentication operations.

    Does not own a repository—operates directly on AdminAccount instances
    that are already managed by the caller's session.
    """

    _secret_key: str

    def __init__(self, *, secret_key: str) -> None:
        """Initialize with the application secret key for encryption.

        Args:
            secret_key: Application secret key for encrypting TOTP secrets.
        """
        self._secret_key = secret_key

    def generate_setup(self, admin: AdminAccount) -> tuple[str, str, list[str]]:
        """Generate TOTP setup data for an admin account.

        Creates a new TOTP secret, encrypts and stores it on the account,
        generates backup codes, and returns the provisioning URI + QR SVG.

        The caller must flush/commit the session to persist changes.

        Args:
            admin: The admin account to set up TOTP for.

        Returns:
            A tuple of (provisioning_uri, qr_svg, backup_codes).

        Raises:
            AuthenticationError: If TOTP is already enabled.
        """
        if admin.totp_enabled:
            raise AuthenticationError("TOTP is already enabled", "TOTP_ALREADY_ENABLED")

        # Generate and encrypt the TOTP secret
        secret = pyotp.random_base32()
        admin.totp_secret_encrypted = encrypt_totp_secret(
            secret, secret_key=self._secret_key
        )

        # Generate provisioning URI
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        uri = totp.provisioning_uri(name=admin.username, issuer_name=TOTP_ISSUER)

        # Generate QR code as SVG
        qr = segno.make(uri)
        svg_buffer = io.BytesIO()
        qr.save(
            svg_buffer, kind="svg", scale=4, dark="currentColor", light="transparent"
        )
        qr_svg = svg_buffer.getvalue().decode()

        # Generate and store backup codes
        backup_codes = generate_backup_codes()
        admin.totp_backup_codes = hash_backup_codes(backup_codes)

        logger.info(
            "totp_setup_generated",
            admin_id=str(admin.id),
            username=admin.username,
        )

        return uri, qr_svg, backup_codes

    def confirm_setup(self, admin: AdminAccount, code: str) -> bool:
        """Confirm TOTP setup by verifying a code from the authenticator.

        The caller provides a TOTP code to prove they have successfully
        configured their authenticator app. On success, totp_enabled is
        set to True.

        Args:
            admin: The admin account completing TOTP setup.
            code: The 6-digit TOTP code from the authenticator app.

        Returns:
            True if the code is valid and TOTP is now enabled.

        Raises:
            AuthenticationError: If no pending TOTP secret exists or already enabled.
        """
        if admin.totp_enabled:
            raise AuthenticationError("TOTP is already enabled", "TOTP_ALREADY_ENABLED")

        if admin.totp_secret_encrypted is None:
            raise AuthenticationError(
                "No TOTP setup in progress", "TOTP_NOT_CONFIGURED"
            )

        secret = self._decrypt_secret(admin)
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)

        if not totp.verify(code, valid_window=1):
            return False

        admin.totp_enabled = True
        logger.info(
            "totp_enabled",
            admin_id=str(admin.id),
            username=admin.username,
        )
        return True

    def verify_code(self, admin: AdminAccount, code: str) -> bool:
        """Verify a TOTP code during login.

        Args:
            admin: The admin account to verify against.
            code: The 6-digit TOTP code.

        Returns:
            True if the code is valid.

        Raises:
            AuthenticationError: If TOTP is not enabled or secret is missing.
        """
        if not admin.totp_enabled or admin.totp_secret_encrypted is None:
            raise AuthenticationError("TOTP is not enabled", "TOTP_NOT_ENABLED")

        secret = self._decrypt_secret(admin)
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        return totp.verify(code, valid_window=1)

    def verify_backup_code(self, admin: AdminAccount, code: str) -> bool:
        """Verify and consume a backup code during login.

        On successful verification, the used code is removed from storage.
        The caller must flush/commit the session to persist the change.

        Args:
            admin: The admin account.
            code: The backup code to verify.

        Returns:
            True if the code is valid and was consumed.

        Raises:
            AuthenticationError: If TOTP is not enabled or no backup codes exist.
        """
        if not admin.totp_enabled:
            raise AuthenticationError("TOTP is not enabled", "TOTP_NOT_ENABLED")

        if admin.totp_backup_codes is None:
            raise AuthenticationError("No backup codes available", "NO_BACKUP_CODES")

        matched, updated_json = verify_backup_code(admin.totp_backup_codes, code)
        if matched:
            admin.totp_backup_codes = updated_json
            logger.info(
                "totp_backup_code_used",
                admin_id=str(admin.id),
                username=admin.username,
            )
        return matched

    def disable(self, admin: AdminAccount) -> None:
        """Disable TOTP for an admin account.

        Clears the encrypted secret, backup codes, and the enabled flag.
        The caller must flush/commit the session.

        Args:
            admin: The admin account.

        Raises:
            AuthenticationError: If TOTP is not currently enabled.
        """
        if not admin.totp_enabled:
            raise AuthenticationError("TOTP is not enabled", "TOTP_NOT_ENABLED")

        admin.totp_enabled = False
        admin.totp_secret_encrypted = None
        admin.totp_backup_codes = None

        logger.info(
            "totp_disabled",
            admin_id=str(admin.id),
            username=admin.username,
        )

    def regenerate_backup_codes(self, admin: AdminAccount) -> list[str]:
        """Generate a fresh set of backup codes, replacing existing ones.

        The caller must flush/commit the session.

        Args:
            admin: The admin account.

        Returns:
            The new list of plaintext backup codes.

        Raises:
            AuthenticationError: If TOTP is not enabled.
        """
        if not admin.totp_enabled:
            raise AuthenticationError("TOTP is not enabled", "TOTP_NOT_ENABLED")

        codes = generate_backup_codes()
        admin.totp_backup_codes = hash_backup_codes(codes)

        logger.info(
            "totp_backup_codes_regenerated",
            admin_id=str(admin.id),
            username=admin.username,
        )
        return codes

    def _decrypt_secret(self, admin: AdminAccount) -> str:
        """Decrypt the TOTP secret from an admin account.

        Args:
            admin: The admin account with an encrypted TOTP secret.

        Returns:
            The decrypted base32-encoded TOTP secret.

        Raises:
            AuthenticationError: If the secret is missing or decryption fails.
        """
        if admin.totp_secret_encrypted is None:
            raise AuthenticationError(
                "TOTP secret not configured", "TOTP_NOT_CONFIGURED"
            )

        try:
            return decrypt_totp_secret(
                admin.totp_secret_encrypted, secret_key=self._secret_key
            )
        except InvalidToken:
            logger.error(
                "totp_decryption_failed",
                admin_id=str(admin.id),
            )
            raise AuthenticationError(
                "Failed to decrypt TOTP secret", "TOTP_DECRYPTION_FAILED"
            ) from None

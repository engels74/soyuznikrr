"""Signed wizard completion tokens for server-side enforcement.

Provides HMAC-based token signing and verification for wizard completion.
Tokens encode the wizard_id and completion timestamp, signed with the
app's SECRET_KEY. Used to prove wizard completion during invitation
redemption — prevents bypassing configured pre-wizard requirements.

Token format: base64(json_payload).hmac_signature
"""

import base64
import hashlib
import hmac
import time

import msgspec
from uuid import UUID


class _WizardTokenPayload(msgspec.Struct, frozen=True):
    """Internal payload for wizard completion tokens."""

    wizard_id: str
    completed_at: float


def sign_wizard_completion(wizard_id: UUID, secret_key: str, /) -> str:
    """Create a signed wizard completion token.

    Args:
        wizard_id: The UUID of the completed wizard (positional-only).
        secret_key: The app secret key for HMAC signing (positional-only).

    Returns:
        A signed token string in the format ``base64_payload.signature``.
    """
    payload = _WizardTokenPayload(
        wizard_id=str(wizard_id),
        completed_at=time.time(),
    )
    payload_bytes = msgspec.json.encode(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()

    signature = hmac.new(
        secret_key.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def verify_wizard_completion(
    token: str,
    expected_wizard_id: UUID,
    secret_key: str,
    /,
    *,
    max_age_seconds: int = 3600,
) -> bool:
    """Verify a signed wizard completion token.

    Checks HMAC signature validity, wizard_id match, and token age.

    Args:
        token: The signed token string (positional-only).
        expected_wizard_id: The wizard ID that must match (positional-only).
        secret_key: The app secret key for HMAC verification (positional-only).
        max_age_seconds: Maximum token age in seconds (keyword-only, default 3600).

    Returns:
        True if the token is valid, False otherwise.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False

        payload_b64, signature = parts

        # Decode and parse payload
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = msgspec.json.decode(payload_bytes, type=_WizardTokenPayload)

        # Verify HMAC signature (constant-time comparison)
        expected_sig = hmac.new(
            secret_key.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return False

        # Verify wizard_id matches
        if payload.wizard_id != str(expected_wizard_id):
            return False

        # Verify token is not expired
        age = time.time() - payload.completed_at
        if age < 0 or age > max_age_seconds:
            return False

    except Exception:
        return False

    return True

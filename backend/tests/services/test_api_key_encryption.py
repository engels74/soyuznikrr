"""Tests for API key encryption service.

Tests cover:
- Fernet+HKDF encrypt/decrypt roundtrip for media server API keys
- HKDF context isolation between API key and TOTP encryption
- Integration: MediaServerService.add() encrypts API keys in the database
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import TestDB
from zondarr.config import Settings
from zondarr.media.registry import ClientRegistry
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.services.api_key_encryption import (
    InvalidToken,
    decrypt_api_key,
    encrypt_api_key,
)
from zondarr.services.media_server import MediaServerService
from zondarr.services.totp_encryption import (
    decrypt_totp_secret,
    encrypt_totp_secret,
)

# Stable test secret key (>= 32 chars)
TEST_SECRET_KEY = "test-secret-key-for-encryption-at-least-32-chars!"  # noqa: S105


# =============================================================================
# API Key Encryption Unit Tests
# =============================================================================


class TestAPIKeyEncryption:
    """Tests for Fernet+HKDF encrypt/decrypt of media server API keys."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encrypting then decrypting returns the original plaintext."""
        api_key = "my-super-secret-api-key-12345"
        encrypted = encrypt_api_key(api_key, secret_key=TEST_SECRET_KEY)
        decrypted = decrypt_api_key(encrypted, secret_key=TEST_SECRET_KEY)
        assert decrypted == api_key

    def test_encrypted_output_differs_from_plaintext(self) -> None:
        """The encrypted string should not contain the plaintext."""
        api_key = "plaintext-api-key-value"
        encrypted = encrypt_api_key(api_key, secret_key=TEST_SECRET_KEY)
        assert encrypted != api_key
        assert api_key not in encrypted

    def test_wrong_key_raises_invalid_token(self) -> None:
        """Decrypting with a different secret key raises InvalidToken."""
        api_key = "test-api-key-for-wrong-key-check"
        encrypted = encrypt_api_key(api_key, secret_key=TEST_SECRET_KEY)
        with pytest.raises(InvalidToken):
            decrypt_api_key(  # pyright: ignore[reportUnusedCallResult]
                encrypted,
                secret_key="a-completely-different-secret-key-32chars!",
            )

    def test_different_hkdf_context_isolation(self) -> None:
        """API key encryption and TOTP encryption use different HKDF contexts.

        A value encrypted with encrypt_api_key cannot be decrypted with
        decrypt_totp_secret and vice versa.
        """
        plaintext = "shared-plaintext-value-for-isolation-test"

        # Encrypt with API key context
        api_encrypted = encrypt_api_key(plaintext, secret_key=TEST_SECRET_KEY)

        # Encrypt with TOTP context
        totp_encrypted = encrypt_totp_secret(plaintext, secret_key=TEST_SECRET_KEY)

        # API-encrypted cannot be decrypted with TOTP decryptor
        with pytest.raises(InvalidToken):
            decrypt_totp_secret(  # pyright: ignore[reportUnusedCallResult]
                api_encrypted, secret_key=TEST_SECRET_KEY
            )

        # TOTP-encrypted cannot be decrypted with API decryptor
        with pytest.raises(InvalidToken):
            decrypt_api_key(  # pyright: ignore[reportUnusedCallResult]
                totp_encrypted, secret_key=TEST_SECRET_KEY
            )


# =============================================================================
# Integration: MediaServerService encrypts API keys
# =============================================================================


class TestMediaServerServiceEncryptsAPIKey:
    """Integration test: MediaServerService.add() stores encrypted API keys."""

    @pytest.mark.asyncio
    async def test_add_encrypts_api_key_in_db(self, db: TestDB) -> None:
        """After add(), the stored api_key is encrypted and can be decrypted back."""
        await db.clean()
        async with db.session_factory() as session:
            repo = MediaServerRepository(session)

            # Mock registry with test_connection returning True
            mock_registry = MagicMock(spec=ClientRegistry)
            mock_registry.registered_types = MagicMock(
                return_value=frozenset({"plex", "jellyfin"})
            )
            mock_client = AsyncMock()
            mock_client.test_connection = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_registry.create_client = MagicMock(return_value=mock_client)

            test_settings = Settings(secret_key=TEST_SECRET_KEY)
            service = MediaServerService(
                repo, registry=mock_registry, settings=test_settings
            )

            plaintext_key = "my-plaintext-api-key-for-integration"
            created = await service.add(
                name="Test Server",
                server_type="plex",
                url="http://plex.local:32400",
                api_key=plaintext_key,
            )
            await session.commit()

            # The stored api_key must NOT be the plaintext value
            assert created.api_key != plaintext_key
            assert plaintext_key not in created.api_key

            # Decrypting it should return the original plaintext
            decrypted = decrypt_api_key(created.api_key, secret_key=TEST_SECRET_KEY)
            assert decrypted == plaintext_key

            # Also verify via a fresh DB read
            retrieved = await repo.get_by_id(created.id)
            assert retrieved is not None
            assert retrieved.api_key != plaintext_key
            assert (
                decrypt_api_key(retrieved.api_key, secret_key=TEST_SECRET_KEY)
                == plaintext_key
            )

"""Repositories for admin authentication entities."""

from datetime import datetime
from typing import override

from sqlalchemy import delete, func, select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.admin import AdminAccount, RefreshToken
from zondarr.repositories.base import Repository


class AdminAccountRepository(Repository[AdminAccount]):
    """Repository for AdminAccount CRUD operations."""

    @property
    @override
    def _model_class(self) -> type[AdminAccount]:
        return AdminAccount

    async def get_by_username(self, username: str) -> AdminAccount | None:
        """Find an admin account by username.

        Args:
            username: The username to search for.

        Returns:
            The AdminAccount if found, None otherwise.
        """
        try:
            stmt = select(AdminAccount).where(AdminAccount.username == username)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get AdminAccount by username",
                operation="get_by_username",
                original=e,
            ) from e

    async def get_by_external_id(
        self, external_id: str, auth_method: str
    ) -> AdminAccount | None:
        """Find an admin account by external ID and auth method.

        Args:
            external_id: The external service identifier.
            auth_method: The authentication method (plex/jellyfin).

        Returns:
            The AdminAccount if found, None otherwise.
        """
        try:
            stmt = select(AdminAccount).where(
                AdminAccount.external_id == external_id,
                AdminAccount.auth_method == auth_method,
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get AdminAccount by external_id",
                operation="get_by_external_id",
                original=e,
            ) from e

    async def count(self) -> int:
        """Count total admin accounts.

        Returns:
            The number of admin accounts in the database.
        """
        try:
            stmt = select(func.count()).select_from(AdminAccount)
            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            raise RepositoryError(
                "Failed to count AdminAccounts",
                operation="count",
                original=e,
            ) from e


class RefreshTokenRepository(Repository[RefreshToken]):
    """Repository for RefreshToken CRUD operations."""

    @property
    @override
    def _model_class(self) -> type[RefreshToken]:
        return RefreshToken

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Find a refresh token by its hash.

        Args:
            token_hash: The SHA-256 hash of the token.

        Returns:
            The RefreshToken if found, None otherwise.
        """
        try:
            stmt = select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(
                "Failed to get RefreshToken by hash",
                operation="get_by_token_hash",
                original=e,
            ) from e

    async def revoke_all_for_admin(self, admin_account_id: object) -> int:
        """Revoke all refresh tokens for an admin account.

        Args:
            admin_account_id: The UUID of the admin account.

        Returns:
            Number of tokens revoked.
        """
        try:
            stmt = select(RefreshToken).where(
                RefreshToken.admin_account_id == admin_account_id,
                RefreshToken.revoked.is_(False),
            )
            result = await self.session.execute(stmt)
            tokens = result.scalars().all()
            count = 0
            for token in tokens:
                token.revoked = True
                count += 1
            return count
        except Exception as e:
            raise RepositoryError(
                "Failed to revoke tokens for admin",
                operation="revoke_all_for_admin",
                original=e,
            ) from e

    async def delete_expired(self, now: datetime) -> int:
        """Delete all expired refresh tokens.

        Args:
            now: Current UTC datetime.

        Returns:
            Number of tokens deleted.
        """
        try:
            stmt = delete(RefreshToken).where(RefreshToken.expires_at < now)
            result = await self.session.execute(stmt)
            return result.rowcount  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        except Exception as e:
            raise RepositoryError(
                "Failed to delete expired tokens",
                operation="delete_expired",
                original=e,
            ) from e

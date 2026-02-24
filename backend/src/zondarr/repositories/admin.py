"""Repositories for admin authentication entities."""

from datetime import datetime
from typing import override
from uuid import uuid4

from sqlalchemy import delete, exists, func, insert, literal, select
from sqlalchemy.exc import IntegrityError

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

    async def create_first_admin(
        self,
        *,
        username: str,
        password_hash: str,
        email: str | None,
        auth_method: str,
    ) -> AdminAccount | None:
        """Create the first admin account if none exists.

        Uses INSERT ... SELECT ... WHERE NOT EXISTS as the primary guard.
        Falls back to catching IntegrityError from the UNIQUE constraint
        on ``username`` to handle PostgreSQL races under READ COMMITTED
        isolation (two transactions can both see "no rows" and attempt
        to insert). A savepoint keeps the outer transaction clean.

        The caller (AuthService.setup_admin) also holds an asyncio.Lock
        to serialize attempts within a single process.

        Args:
            username: Admin username.
            password_hash: Pre-hashed password.
            email: Optional email address.
            auth_method: Authentication method (e.g. "local").

        Returns:
            The created AdminAccount, or None if an admin already exists.
        """
        try:
            admin_id = uuid4()
            columns = [
                AdminAccount.__table__.c.id,
                AdminAccount.__table__.c.username,
                AdminAccount.__table__.c.password_hash,
                AdminAccount.__table__.c.email,
                AdminAccount.__table__.c.auth_method,
                AdminAccount.__table__.c.enabled,
            ]
            values = select(
                literal(admin_id.hex).label("id"),
                literal(username).label("username"),
                literal(password_hash).label("password_hash"),
                literal(email).label("email"),
                literal(auth_method).label("auth_method"),
                literal(True).label("enabled"),
            ).where(~exists(select(AdminAccount.id)))

            table = AdminAccount.__table__
            stmt = insert(table).from_select(columns, values)  # pyright: ignore[reportArgumentType]
            result = await self.session.execute(stmt)

            if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                return None

            return await self.get_by_id(admin_id)
        except IntegrityError:
            # Concurrent insert won the race — UNIQUE(username) prevented
            # the duplicate. The caller (setup_admin) will raise
            # AuthenticationError, and the DI layer rolls back the session.
            return None
        except Exception as e:
            raise RepositoryError(
                "Failed to create first admin",
                operation="create_first_admin",
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

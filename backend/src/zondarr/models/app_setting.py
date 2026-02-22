"""AppSetting model for key-value application settings.

Provides a simple key-value store for application settings that can be
managed via the admin API. Uses a string primary key (settings are
naturally keyed by name, not UUID).
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zondarr.models.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    """Key-value application setting.

    Stores application-level configuration that can be managed at runtime
    via the admin API, with optional environment variable overrides.

    Attributes:
        key: Setting identifier (primary key, max 255 chars).
        value: Setting value (nullable text).
    """

    __tablename__: str = "app_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, default=None)

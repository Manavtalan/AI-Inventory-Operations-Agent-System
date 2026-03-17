"""
SQLAlchemy 2.0 declarative base and shared column mixin.

Every domain model (ShopifyEvent, InventorySnapshot, etc.) should inherit from
both Base and TimestampMixin:

    class MyModel(TimestampMixin, Base):
        __tablename__ = "my_models"
        ...

This gives every table:
    - id          UUID primary key (auto-generated)
    - created_at  Timestamp (set by database on INSERT)
    - updated_at  Timestamp (set by database on INSERT + UPDATE)
    - is_deleted  Boolean (soft-delete flag, default False)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    All models must inherit from this class so Alembic can discover them via
    Base.metadata when autogenerating migrations.
    """

    pass


class TimestampMixin:
    """Common columns added to every model table.

    Inherit alongside Base:
        class Foo(TimestampMixin, Base):
            __tablename__ = "foos"
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key — UUID v4 generated in application layer.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Row creation timestamp (UTC, set by DB).",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Row last-update timestamp (UTC, updated by DB on every write).",
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Soft-delete flag. Filter with is_deleted=False in all queries.",
    )

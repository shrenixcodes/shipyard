import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ShipStatus(str, enum.Enum):
    KEEL_LAID = "keel_laid"
    UNDER_CONSTRUCTION = "under_construction"
    LAUNCHED = "launched"
    COMMISSIONED = "commissioned"
    DECOMMISSIONED = "decommissioned"


class Ship(Base):
    __tablename__ = "ships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    status: Mapped[ShipStatus] = mapped_column(
        Enum(ShipStatus, name="ship_status", native_enum=False, length=32),
        nullable=False,
        default=ShipStatus.KEEL_LAID,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

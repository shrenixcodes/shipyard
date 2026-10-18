import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ShipStatus


class ShipCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    status: ShipStatus = ShipStatus.KEEL_LAID


class ShipUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: ShipStatus | None = None


class ShipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: ShipStatus
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    detail: str

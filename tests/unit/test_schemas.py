import pytest
from pydantic import ValidationError

from app.models import ShipStatus
from app.schemas import ShipCreate, ShipUpdate

pytestmark = pytest.mark.unit


def test_ship_create_defaults_to_keel_laid():
    ship = ShipCreate(name="Discovery")
    assert ship.status == ShipStatus.KEEL_LAID


def test_ship_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        ShipCreate(name="")


def test_ship_create_rejects_overlong_name():
    with pytest.raises(ValidationError):
        ShipCreate(name="x" * 121)


def test_ship_update_allows_partial_fields():
    update = ShipUpdate(status=ShipStatus.LAUNCHED)
    dumped = update.model_dump(exclude_unset=True)
    assert dumped == {"status": ShipStatus.LAUNCHED}


def test_ship_create_rejects_unknown_status():
    with pytest.raises(ValidationError):
        ShipCreate(name="Discovery", status="not-a-real-status")

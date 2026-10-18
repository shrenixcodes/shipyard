import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ship
from app.schemas import ErrorResponse, ShipCreate, ShipRead, ShipUpdate

router = APIRouter(prefix="/ships", tags=["ships"])

NOT_FOUND_RESPONSE = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
CONFLICT_RESPONSE = {status.HTTP_409_CONFLICT: {"model": ErrorResponse}}


@router.post(
    "",
    response_model=ShipRead,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT_RESPONSE,
)
async def create_ship(payload: ShipCreate, session: AsyncSession = Depends(get_session)) -> Ship:
    ship = Ship(name=payload.name, status=payload.status)
    session.add(ship)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="a ship with this name already exists"
        ) from exc
    await session.refresh(ship)
    return ship


@router.get("", response_model=list[ShipRead])
async def list_ships(session: AsyncSession = Depends(get_session)) -> list[Ship]:
    result = await session.execute(select(Ship).order_by(Ship.created_at))
    return list(result.scalars().all())


@router.get("/{ship_id}", response_model=ShipRead, responses=NOT_FOUND_RESPONSE)
async def get_ship(ship_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Ship:
    ship = await session.get(Ship, ship_id)
    if ship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ship not found")
    return ship


@router.patch(
    "/{ship_id}",
    response_model=ShipRead,
    responses={**NOT_FOUND_RESPONSE, **CONFLICT_RESPONSE},
)
async def update_ship(
    ship_id: uuid.UUID, payload: ShipUpdate, session: AsyncSession = Depends(get_session)
) -> Ship:
    ship = await session.get(Ship, ship_id)
    if ship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ship not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ship, field, value)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="a ship with this name already exists"
        ) from exc
    await session.refresh(ship)
    return ship


@router.delete("/{ship_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND_RESPONSE)
async def delete_ship(ship_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    ship = await session.get(Ship, ship_id)
    if ship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ship not found")
    await session.delete(ship)
    await session.commit()

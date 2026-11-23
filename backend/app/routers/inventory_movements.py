
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.inventory_movements import InventoryMovement
from app.schemas.inventory_movement import InventoryMovementResponse
from app.security.dependencies import get_current_admin

router = APIRouter(
    prefix="/api/inventory-movements",
    tags=["Inventory Movements"],
)

@router.get(
    "/",
    response_model=list[InventoryMovementResponse],
)
def get_inventory_movements(
    inventory_id: UUID | None = Query(default=None),
    movement_type: str | None = Query(default=None, min_length=1, max_length=30),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> list[InventoryMovementResponse]:
    """Retrieve inventory movement history with optional filters."""

    statement = select(InventoryMovement)

    if inventory_id is not None:
        statement = statement.where(
            InventoryMovement.inventory_id == inventory_id
        )

    if movement_type is not None:
        statement = statement.where(
            InventoryMovement.movement_type == movement_type.strip()
        )

    statement = (
        statement
        .order_by(InventoryMovement.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    movements = db.scalars(statement).all()

    return [
        InventoryMovementResponse.model_validate(movement)
        for movement in movements
    ]

@router.get(
    "/{movement_id}",
    response_model=InventoryMovementResponse,
)
def get_inventory_movement(
    movement_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> InventoryMovementResponse:
    """Retrieve one inventory movement record."""

    movement = db.get(InventoryMovement, movement_id)

    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory movement not found.",
        )

    return InventoryMovementResponse.model_validate(movement)

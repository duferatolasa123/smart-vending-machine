
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.inventory import Inventory
from app.models.inventory_movements import InventoryMovement
from app.models.machine_slots import MachineSlot
from app.schemas.inventory import InventoryAdjustment, InventoryResponse
from app.security.dependencies import get_current_admin


router = APIRouter(
    prefix="/api/inventory",
    tags=["Inventory"],
)


@router.get(
    "/",
    response_model=list[InventoryResponse],
)
def get_inventory(
    machine_slot_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[InventoryResponse]:
    """Retrieve inventory records, optionally filtered by machine slot."""

    statement = select(Inventory)

    if machine_slot_id is not None:
        statement = statement.where(
            Inventory.machine_slot_id == machine_slot_id
        )

    statement = statement.order_by(Inventory.created_at.desc())

    inventory_records = db.scalars(statement).all()

    return [
        InventoryResponse.model_validate(record)
        for record in inventory_records
    ]


@router.get(
    "/{inventory_id}",
    response_model=InventoryResponse,
)
def get_inventory_by_id(
    inventory_id: UUID,
    db: Session = Depends(get_db),
) -> InventoryResponse:
    """Retrieve one inventory record."""

    inventory = db.get(Inventory, inventory_id)

    if inventory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory record not found.",
        )

    return InventoryResponse.model_validate(inventory)


@router.post(
    "/{machine_slot_id}/initialize",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_inventory(
    machine_slot_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> InventoryResponse:
    """Create an empty inventory record for an existing machine slot."""

    slot = db.get(MachineSlot, machine_slot_id)

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Machine slot not found.",
        )

    if not slot.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot initialize inventory for an inactive machine slot.",
        )

    existing_inventory = db.scalar(
        select(Inventory).where(
            Inventory.machine_slot_id == machine_slot_id
        )
    )

    if existing_inventory is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory has already been initialized for this machine slot.",
        )

    inventory = Inventory(
        machine_slot_id=machine_slot_id,
        quantity=0,
        reserved_quantity=0,
    )

    try:
        db.add(inventory)
        db.commit()
        db.refresh(inventory)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory already exists for this slot or a database constraint was violated.",
        )

    return InventoryResponse.model_validate(inventory)


@router.post(
    "/{inventory_id}/adjustments",
    response_model=InventoryResponse,
)
def adjust_inventory(
    inventory_id: UUID,
    adjustment: InventoryAdjustment,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> InventoryResponse:
    """Adjust stock and record the corresponding inventory movement."""

    if adjustment.quantity_changed == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity change must not be zero.",
        )

    inventory = db.scalar(
        select(Inventory)
        .where(Inventory.id == inventory_id)
        .with_for_update()
    )

    if inventory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory record not found.",
        )

    slot = db.get(MachineSlot, inventory.machine_slot_id)

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated machine slot not found.",
        )

    new_quantity = inventory.quantity + adjustment.quantity_changed

    if new_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient stock for this adjustment.",
        )

    if new_quantity < inventory.reserved_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Adjustment would reduce stock below the reserved quantity.",
        )

    if new_quantity > slot.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adjustment exceeds slot capacity of {slot.capacity}.",
        )

    movement = InventoryMovement(
        inventory_id=inventory.id,
        movement_type=adjustment.movement_type.strip(),
        quantity_changed=adjustment.quantity_changed,
        unit_cost=(
            Decimal(str(adjustment.unit_cost))
            if adjustment.unit_cost is not None
            else None
        ),
        reference=adjustment.reference,
        notes=adjustment.notes,
        performed_by_admin_id=current_admin.id,
    )

    inventory.quantity = new_quantity

    try:
        db.add(movement)
        db.commit()
        db.refresh(inventory)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory adjustment violates a database constraint.",
        )

    return InventoryResponse.model_validate(inventory)

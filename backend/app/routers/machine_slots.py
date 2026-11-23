
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.machines import Machine
from app.models.machine_slots import MachineSlot
from app.models.products import Product
from app.schemas.machine_slot import (
    MachineSlotCreate,
    MachineSlotResponse,
    MachineSlotUpdate,
)
from app.security.dependencies import get_current_admin


router = APIRouter(
    prefix="/api/machine-slots",
    tags=["Machine Slots"],
)


@router.get(
    "/",
    response_model=list[MachineSlotResponse],
)
def get_machine_slots(
    machine_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MachineSlotResponse]:
    """Retrieve active machine slots, optionally filtered by machine."""

    statement = select(MachineSlot).where(
        MachineSlot.is_active.is_(True)
    )

    if machine_id is not None:
        statement = statement.where(
            MachineSlot.machine_id == machine_id
        )

    statement = statement.order_by(
        MachineSlot.machine_id,
        MachineSlot.slot_number,
    )

    slots = db.scalars(statement).all()

    return [
        MachineSlotResponse.model_validate(slot)
        for slot in slots
    ]


@router.post(
    "/",
    response_model=MachineSlotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_machine_slot(
    slot_data: MachineSlotCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> MachineSlotResponse:
    """Create a slot for an existing vending machine."""

    machine = db.scalar(
        select(Machine).where(
            Machine.id == slot_data.machine_id,
            Machine.is_active.is_(True),
        )
    )

    if machine is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected machine does not exist or is inactive.",
        )

    if slot_data.product_id is not None:
        product = db.scalar(
            select(Product).where(
                Product.id == slot_data.product_id,
                Product.is_active.is_(True),
            )
        )

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected product does not exist or is inactive.",
            )

    slot = MachineSlot(
        machine_id=slot_data.machine_id,
        slot_code=slot_data.slot_code.strip(),
        slot_number=slot_data.slot_number,
        product_id=slot_data.product_id,
            motor_channel=slot_data.motor_channel,
        capacity=slot_data.capacity,
        is_active=slot_data.is_active,
    )

    try:
        db.add(slot)
        db.commit()
        db.refresh(slot)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A slot with this code or number already exists for this machine, or a database constraint was violated.",
        )

    return MachineSlotResponse.model_validate(slot)


@router.patch(
    "/{slot_id}",
    response_model=MachineSlotResponse,
)
def update_machine_slot(
    slot_id: UUID,
    slot_data: MachineSlotUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> MachineSlotResponse:
    """Update a slot's product assignment, capacity, or active status."""

    slot = db.get(MachineSlot, slot_id)

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Machine slot not found.",
        )

    update_data = slot_data.model_dump(exclude_unset=True)

    if "product_id" in update_data:
        product_id = update_data["product_id"]

        if product_id is not None:
            product = db.scalar(
                select(Product).where(
                    Product.id == product_id,
                    Product.is_active.is_(True),
                )
            )

            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The selected product does not exist or is inactive.",
                )

        slot.product_id = product_id
    if "motor_channel" in update_data:
        slot.motor_channel = update_data["motor_channel"]

    if "capacity" in update_data:
        slot.capacity = update_data["capacity"]

    if "is_active" in update_data:
        slot.is_active = update_data["is_active"]

    try:
        db.commit()
        db.refresh(slot)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The machine slot update violates a database constraint.",
        )

    return MachineSlotResponse.model_validate(slot)

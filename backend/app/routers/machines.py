
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.machines import Machine
from app.schemas.machine import MachineCreate, MachineResponse
from app.security.dependencies import get_current_admin


router = APIRouter(
    prefix="/api/machines",
    tags=["Machines"],
)


@router.get(
    "/",
    response_model=list[MachineResponse],
)
def get_machines(
    db: Session = Depends(get_db),
) -> list[MachineResponse]:
    """
    Retrieve all active vending machines.
    """

    statement = (
        select(Machine)
        .where(Machine.is_active.is_(True))
        .order_by(Machine.name.asc())
    )

    machines = db.scalars(statement).all()

    return [
        MachineResponse.model_validate(machine)
        for machine in machines
    ]


@router.post(
    "/",
    response_model=MachineResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_machine(
    machine_data: MachineCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> MachineResponse:
    """
    Register a new vending machine.
    Requires an authenticated, active administrator.
    """

    existing_machine = db.scalar(
        select(Machine).where(
            Machine.machine_code == machine_data.machine_code.strip()
        )
    )

    if existing_machine is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A machine with this machine code already exists.",
        )

    if machine_data.serial_number:
        existing_serial = db.scalar(
            select(Machine).where(
                Machine.serial_number == machine_data.serial_number.strip()
            )
        )

        if existing_serial is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A machine with this serial number already exists.",
            )

    machine = Machine(
        machine_code=machine_data.machine_code.strip(),
        name=machine_data.name.strip(),
        location_description=machine_data.location_description,
        serial_number=(
            machine_data.serial_number.strip()
            if machine_data.serial_number
            else None
        ),
        firmware_version=machine_data.firmware_version,
        is_active=machine_data.is_active,
        status="offline",
    )

    try:
        db.add(machine)
        db.commit()
        db.refresh(machine)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The machine could not be registered because of a database conflict.",
        )

    return MachineResponse.model_validate(machine)

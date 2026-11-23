
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.machine_events import MachineEvent
from app.models.machines import Machine
from app.schemas.machine_event import (
    MachineEventCreate,
    MachineEventResponse,
)
from app.security.dependencies import get_current_admin

router = APIRouter(
    prefix="/api/machine-events",
    tags=["Machine Events"],
)


VALID_SEVERITIES = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


@router.get(
    "/",
    response_model=list[MachineEventResponse],
)
def get_machine_events(
    machine_id: UUID | None = Query(default=None),
    event_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    severity: str | None = Query(
        default=None,
        min_length=1,
        max_length=20,
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> list[MachineEventResponse]:
    """Retrieve machine events with optional filters."""

    statement = select(MachineEvent)

    if machine_id is not None:
        statement = statement.where(
            MachineEvent.machine_id == machine_id
        )

    if event_type is not None:
        statement = statement.where(
            MachineEvent.event_type == event_type.strip()
        )

    if severity is not None:
        normalized_severity = severity.strip().upper()

        if normalized_severity not in VALID_SEVERITIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid event severity.",
            )

        statement = statement.where(
            MachineEvent.severity == normalized_severity
        )

    statement = (
        statement
        .order_by(MachineEvent.occurred_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return [
        MachineEventResponse.model_validate(event)
        for event in db.scalars(statement).all()
    ]


@router.get(
    "/{event_id}",
    response_model=MachineEventResponse,
)
def get_machine_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> MachineEventResponse:
    """Retrieve one machine event."""

    event = db.get(MachineEvent, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Machine event not found.",
        )

    return MachineEventResponse.model_validate(event)


@router.post(
    "/{machine_id}",
    response_model=MachineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_machine_event(
    machine_id: UUID,
    event_data: MachineEventCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> MachineEventResponse:
    """Register a machine event as an authenticated administrator."""

    machine = db.get(Machine, machine_id)

    if machine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Machine not found.",
        )

    normalized_severity = event_data.severity.strip().upper()

    if normalized_severity not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid severity. Allowed values: "
                "DEBUG, INFO, WARNING, ERROR, CRITICAL."
            ),
        )

    event = MachineEvent(
        machine_id=machine_id,
        event_type=event_data.event_type.strip(),
        severity=normalized_severity,
        event_code=(
            event_data.event_code.strip()
            if event_data.event_code
            else None
        ),
        message=event_data.message,
        event_data=event_data.event_data,
        occurred_at=event_data.occurred_at,
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Machine event could not be saved.",
        )

    return MachineEventResponse.model_validate(event)

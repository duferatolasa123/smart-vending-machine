
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.dispense_jobs import DispenseJob
from app.schemas.dispense_job import DispenseJobResponse
from app.security.dependencies import get_current_admin

router = APIRouter(
    prefix="/api/dispense-jobs",
    tags=["Dispense Jobs"],
)

@router.get(
    "/",
    response_model=list[DispenseJobResponse],
)
def get_dispense_jobs(
    machine_id: UUID | None = Query(default=None),
    order_id: UUID | None = Query(default=None),
    job_status: str | None = Query(
        default=None,
        alias="status",
        min_length=1,
        max_length=30,
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> list[DispenseJobResponse]:
    """Retrieve dispense jobs with optional filters."""

    statement = select(DispenseJob)

    if machine_id is not None:
        statement = statement.where(
            DispenseJob.machine_id == machine_id
        )

    if order_id is not None:
        statement = statement.where(
            DispenseJob.order_id == order_id
        )

    if job_status is not None:
        statement = statement.where(
            DispenseJob.status == job_status.strip().upper()
        )

    statement = (
        statement
        .order_by(DispenseJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return [
        DispenseJobResponse.model_validate(job)
        for job in db.scalars(statement).all()
    ]

@router.get(
    "/{job_id}",
    response_model=DispenseJobResponse,
)
def get_dispense_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> DispenseJobResponse:
    """Retrieve one dispense job."""

    job = db.get(DispenseJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispense job not found.",
        )

    return DispenseJobResponse.model_validate(job)

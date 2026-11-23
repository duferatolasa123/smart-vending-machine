
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admins import Admin
from app.schemas.admin import AdminLogin, AdminPasswordChange, AdminResponse
from app.schemas.token import TokenResponse
from app.security.dependencies import get_current_admin
from app.services.admin_auth_service import (
    authenticate_admin,
    change_admin_password,
    get_admin_response_data,
)


router = APIRouter(
    prefix="/api/admin/auth",
    tags=["Administrator Authentication"],
)


def get_client_ip(request: Request) -> str | None:
    """Get the direct client IP address."""

    if request.client is None:
        return None

    return request.client.host


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Administrator login",
)
def admin_login(
    credentials: AdminLogin,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate an administrator and return a JWT."""

    result = authenticate_admin(
        db=db,
        email=str(credentials.email),
        password=credentials.password.get_secret_value(),
        ip_address=get_client_ip(request),
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or inactive account.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _, token = result

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=AdminResponse,
    summary="Get current administrator",
)
def get_my_profile(
    current_admin: Admin = Depends(get_current_admin),
) -> dict[str, Any]:
    """Return the authenticated administrator's profile."""

    return get_admin_response_data(current_admin)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change administrator password",
)
def change_my_password(
    password_data: AdminPasswordChange,
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Change the password of the authenticated administrator."""

    try:
        change_admin_password(
            db=db,
            admin=current_admin,
            current_password=(
                password_data.current_password.get_secret_value()
            ),
            new_password=(
                password_data.new_password.get_secret_value()
            ),
            ip_address=get_client_ip(request),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {"message": "Password changed successfully."}


from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.security.token import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/admin/auth/login"
)


def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """Retrieve the administrator associated with the JWT."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError("Token subject must be a UUID string.")
        admin_id = UUID(subject)

    except (ValueError, InvalidTokenError, KeyError, TypeError):
        raise credentials_exception

    admin = db.scalar(
        select(Admin).where(Admin.id == admin_id)
    )

    if admin is None or not admin.is_active:
        raise credentials_exception

    return admin


def require_roles(*allowed_roles: str):
    """Restrict an endpoint to administrators with specified roles."""

    allowed = {role.upper() for role in allowed_roles}

    def role_checker(
        current_admin: Admin = Depends(get_current_admin),
    ) -> Admin:

        admin_roles = {
            role.code.upper()
            for role in current_admin.roles
        }

        if not admin_roles.intersection(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_admin

    return role_checker

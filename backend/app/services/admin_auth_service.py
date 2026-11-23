
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admins import Admin
from app.models.audit_logs import AuditLog
from app.security.password import hash_password, verify_password
from app.security.token import create_access_token


def authenticate_admin(
    db: Session,
    email: str,
    password: str,
    ip_address: str | None = None,
) -> tuple[Admin, str] | None:
    """Verify administrator credentials and create an access token."""

    normalized_email = email.strip().lower()

    admin = db.scalar(
        select(Admin).where(Admin.email == normalized_email)
    )

    if admin is None:
        return None

    if not admin.is_active:
        return None

    if not verify_password(password, admin.password_hash):
        return None

    now = datetime.now(timezone.utc)
    admin.last_login_at = now

    db.add(
        AuditLog(
            admin_id=admin.id,
            action="ADMIN_LOGIN",
            entity_type="ADMIN",
            entity_id=str(admin.id),
            description="Administrator successfully logged in.",
            ip_address=ip_address,
        )
    )

    token = create_access_token(admin.id)

    db.commit()
    db.refresh(admin)

    return admin, token


def change_admin_password(
    db: Session,
    admin: Admin,
    current_password: str,
    new_password: str,
    ip_address: str | None = None,
) -> None:
    """Verify the current password and save a new password hash."""

    if not verify_password(current_password, admin.password_hash):
        raise ValueError("Current password is incorrect.")

    if current_password == new_password:
        raise ValueError(
            "The new password must be different from the current password."
        )

    admin.password_hash = hash_password(new_password)

    db.add(
        AuditLog(
            admin_id=admin.id,
            action="ADMIN_PASSWORD_CHANGED",
            entity_type="ADMIN",
            entity_id=str(admin.id),
            description="Administrator changed their password.",
            ip_address=ip_address,
        )
    )

    db.commit()


def get_admin_response_data(admin: Admin) -> dict[str, Any]:
    """Convert an administrator model into safe response data."""

    return {
        "id": admin.id,
        "full_name": admin.full_name,
        "email": admin.email,
        "is_active": admin.is_active,
        "last_login_at": admin.last_login_at,
        "roles": sorted(role.code for role in admin.roles),
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
    }

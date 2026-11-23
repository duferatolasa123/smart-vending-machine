
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.admins import Admin
from app.models.roles import Role
from app.security.password import hash_password


class AdminUpdateData(TypedDict, total=False):
    """Validated fields that may be changed on an administrator."""

    full_name: str | None
    email: str | None
    is_active: bool | None


def get_admin_by_id(db: Session, admin_id: UUID) -> Admin | None:
    return db.scalar(
        select(Admin)
        .options(selectinload(Admin.roles))
        .where(Admin.id == admin_id)
    )


def get_all_admins(db: Session) -> list[Admin]:
    return list(
        db.scalars(
            select(Admin)
            .options(selectinload(Admin.roles))
            .order_by(Admin.created_at.desc())
        ).all()
    )


def _require_admin(db: Session, admin_id: UUID) -> Admin:
    admin = get_admin_by_id(db, admin_id)
    if admin is None:
        raise LookupError(
            f"Administrator {admin_id} was not found after update."
        )
    return admin


def create_admin(
    db: Session,
    full_name: str,
    email: str,
    password: str,
    role_codes: list[str],
) -> Admin:
    normalized_email = email.strip().lower()

    existing = db.scalar(
        select(Admin).where(Admin.email == normalized_email)
    )

    if existing:
        raise ValueError("An administrator with this email already exists.")

    roles = list(
        db.scalars(
            select(Role).where(Role.code.in_(role_codes))
        ).all()
    )

    found_codes = {role.code.upper() for role in roles}
    missing_codes = set(role_codes) - found_codes

    if missing_codes:
        raise ValueError(
            f"Unknown role codes: {', '.join(sorted(missing_codes))}"
        )

    admin = Admin(
        full_name=full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        is_active=True,
        roles=roles,
    )

    db.add(admin)
    db.commit()

    return _require_admin(db, admin.id)


def update_admin(
    db: Session,
    admin: Admin,
    update_data: AdminUpdateData,
) -> Admin:
    email_update = update_data.get("email")
    new_email: str | None = None
    if email_update is not None:
        new_email = email_update.strip().lower()

        existing = db.scalar(
            select(Admin).where(
                Admin.email == new_email,
                Admin.id != admin.id,
            )
        )

        if existing:
            raise ValueError(
                "Another administrator already uses this email."
            )

        update_data["email"] = new_email

    full_name = update_data.get("full_name")
    if full_name is not None:
        admin.full_name = full_name

    if new_email is not None:
        admin.email = new_email

    is_active = update_data.get("is_active")
    if is_active is not None:
        admin.is_active = is_active

    db.commit()

    return _require_admin(db, admin.id)


def assign_admin_roles(
    db: Session,
    admin: Admin,
    role_codes: list[str],
) -> Admin:
    roles = list(
        db.scalars(
            select(Role).where(Role.code.in_(role_codes))
        ).all()
    )

    found_codes = {role.code.upper() for role in roles}
    missing_codes = set(role_codes) - found_codes

    if missing_codes:
        raise ValueError(
            f"Unknown role codes: {', '.join(sorted(missing_codes))}"
        )

    admin.roles = roles

    db.commit()

    return _require_admin(db, admin.id)

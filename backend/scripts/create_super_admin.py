
import sys
from getpass import getpass
from pathlib import Path

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.admins import Admin
from app.models.roles import Role
from app.security.password import hash_password


ROLE_DEFINITIONS = [
    {
        "code": "SUPER_ADMIN",
        "name": "Super Administrator",
        "description": "Full access to all administrative functions.",
    },
    {
        "code": "ADMIN",
        "name": "Administrator",
        "description": "General machine administration.",
    },
    {
        "code": "INVENTORY_MANAGER",
        "name": "Inventory Manager",
        "description": "Manage products and inventory.",
    },
    {
        "code": "OPERATOR",
        "name": "Machine Operator",
        "description": "Monitor and operate vending machines.",
    },
    {
        "code": "VIEWER",
        "name": "Read Only Viewer",
        "description": "View permitted dashboard information.",
    },
]


def read_email() -> str:
    """Read and validate an email address."""

    adapter = TypeAdapter(EmailStr)

    while True:
        email = input("Super Admin email: ").strip().lower()

        try:
            return str(adapter.validate_python(email))
        except ValidationError:
            print("Please enter a valid email address.")


def read_password() -> str:
    """Read and confirm a strong initial password."""

    while True:
        password = getpass("Super Admin password: ")

        if len(password) < 12:
            print("Password must contain at least 12 characters.")
            continue

        if len(password) > 128:
            print("Password must not exceed 128 characters.")
            continue

        confirmation = getpass("Confirm password: ")

        if password != confirmation:
            print("Passwords do not match.")
            continue

        return password


def create_super_admin() -> None:
    """Create the first administrator and required system roles."""

    db = SessionLocal()

    try:
        existing_admin = db.scalar(
            select(Admin).limit(1)
        )

        if existing_admin is not None:
            print(
                "An administrator already exists. "
                "Initial setup has been stopped."
            )
            return

        print("\n=== Smart Vending Machine: Initial Admin Setup ===\n")

        full_name = input("Super Admin full name: ").strip()

        if len(full_name) < 2 or len(full_name) > 150:
            print("Full name must contain 2 to 150 characters.")
            return

        email = read_email()

        password = read_password()

        super_admin_role = None

        for role_data in ROLE_DEFINITIONS:
            role = db.scalar(
                select(Role).where(
                    Role.code == role_data["code"]
                )
            )

            if role is None:
                role = Role(
                    **role_data,
                    is_system=True,
                )
                db.add(role)

            if role_data["code"] == "SUPER_ADMIN":
                super_admin_role = role

        db.flush()

        admin = Admin(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            roles=[super_admin_role],
        )

        db.add(admin)
        db.commit()

        print("\nINITIAL SUPER ADMIN CREATED SUCCESSFULLY.")
        print(f"Email: {email}")
        print("Password: saved securely as a password hash.")
        print("\nYou can now log in through the administrator API.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_super_admin()

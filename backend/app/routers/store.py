from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import Inventory
from app.models.machine_slots import MachineSlot
from app.models.machines import Machine
from app.models.products import Product
from app.schemas.store import StoreCatalogItem, StoreCatalogResponse

router = APIRouter(prefix="/api/store", tags=["Store"])


@router.get("/catalog", response_model=StoreCatalogResponse)
def get_store_catalog(
    machine_id: UUID = Query(),
    db: Session = Depends(get_db),
) -> StoreCatalogResponse:
    """Return purchasable products and stock for one active machine."""

    machine = db.scalar(
        select(Machine).where(
            Machine.id == machine_id,
            Machine.is_active.is_(True),
            Machine.status == "online",
        )
    )
    if machine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The selected vending machine is unavailable.",
        )

    rows = db.execute(
        select(MachineSlot, Product, Inventory)
        .join(Product, Product.id == MachineSlot.product_id)
        .outerjoin(Inventory, Inventory.machine_slot_id == MachineSlot.id)
        .where(
            MachineSlot.machine_id == machine.id,
            MachineSlot.is_active.is_(True),
            Product.is_active.is_(True),
        )
        .order_by(MachineSlot.slot_number)
    ).all()

    products = [
        StoreCatalogItem(
            product_id=product.id,
            machine_slot_id=slot.id,
            slot_code=slot.slot_code,
            name=product.name,
            description=product.description,
            price=product.price,
            image_path=product.image_path,
            available_quantity=(
                inventory.available_quantity if inventory is not None else 0
            ),
        )
        for slot, product, inventory in rows
    ]
    return StoreCatalogResponse(
        machine_id=machine.id,
        machine_code=machine.machine_code,
        machine_name=machine.name,
        products=products,
    )

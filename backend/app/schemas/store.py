from decimal import Decimal
from uuid import UUID

from app.schemas.common import BaseSchema


class StoreCatalogItem(BaseSchema):
    product_id: UUID
    machine_slot_id: UUID
    slot_code: str
    name: str
    description: str | None
    price: Decimal
    image_path: str | None
    available_quantity: int


class StoreCatalogResponse(BaseSchema):
    machine_id: UUID
    machine_code: str
    machine_name: str
    products: list[StoreCatalogItem]

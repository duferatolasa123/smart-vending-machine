"""Create a small, repeatable local catalog for the SmartVend demo."""

from decimal import Decimal

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models.categories import Category
from app.models.inventory import Inventory
from app.models.machine_slots import MachineSlot
from app.models.machines import Machine
from app.models.products import Product


PRODUCTS = (
    {
        "slot_code": "A1",
        "slot_number": 1,
        "sku": "WATER-1L",
        "name": "Water 1 L",
        "description": "Bottled water, 1 litre",
        "image_path": "/assets/products/water-1l.jpg",
        "price": Decimal("60.00"),
        "quantity": 12,
        "capacity": 20,
        "motor_channel": 1,
    },
    {
        "slot_code": "A2",
        "slot_number": 2,
        "sku": "MIRINDA",
        "name": "Mirinda",
        "description": "Orange soft drink",
        "image_path": "/assets/products/mirinda.jpg",
        "price": Decimal("80.00"),
        "quantity": 8,
        "capacity": 15,
        "motor_channel": 2,
    },
    {
        "slot_code": "A3",
        "slot_number": 3,
        "sku": "COCA-COLA",
        "name": "Coca-Cola",
        "description": "Chilled Coca-Cola",
        "image_path": "/assets/products/cocacola.jpg",
        "price": Decimal("80.00"),
        "quantity": 10,
        "capacity": 15,
        "motor_channel": 3,
    },
    {
        "slot_code": "A4",
        "slot_number": 4,
        "sku": "SUN-CHIPS",
        "name": "Sun Chips",
        "description": "Crispy Sun Chips",
        "image_path": "/assets/products/sunchips.jpg",
        "price": Decimal("40.00"),
        "quantity": 10,
        "capacity": 12,
        "motor_channel": 4,
    },
    {
        "slot_code": "A5",
        "slot_number": 5,
        "sku": "CHOCOLATE",
        "name": "Chocolate",
        "description": "Chocolate bar",
        "image_path": "/assets/products/chocolate.jpg",
        "price": Decimal("60.00"),
        "quantity": 9,
        "capacity": 12,
        "motor_channel": 5,
    },
    {
        "slot_code": "A6",
        "slot_number": 6,
        "sku": "CAPPUCCINO",
        "name": "Cappuccino",
        "description": "Cappuccino drink",
        "image_path": "/assets/products/cappuchino.jpg",
        "price": Decimal("20.00"),
        "quantity": 8,
        "capacity": 12,
        "motor_channel": 6,
    },
)


def seed_demo_data() -> None:
    # This is intended for local development only. Production data should be
    # created through the authenticated admin APIs and migrations.
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        category = db.scalar(
            select(Category).where(Category.name == "Demo Snacks")
        )
        if category is None:
            category = Category(
                name="Demo Snacks",
                description="Products used by the local SmartVend demo.",
                is_active=True,
            )
            db.add(category)
            db.flush()
        else:
            category.is_active = True

        machine = db.scalar(
            select(Machine).where(Machine.machine_code == "SMARTVEND-DEMO")
        )
        if machine is None:
            machine = Machine(
                machine_code="SMARTVEND-DEMO",
                name="SmartVend Demo",
                location_description="Local development kiosk",
                serial_number="DEMO-001",
                firmware_version="demo-1.0",
                status="online",
                is_active=True,
            )
            db.add(machine)
            db.flush()
        else:
            machine.status = "online"
            machine.is_active = True

        for item in PRODUCTS:
            product = db.scalar(
                select(Product).where(Product.sku == item["sku"])
            )
            if product is None:
                product = Product(
                    category_id=category.id,
                    name=item["name"],
                    sku=item["sku"],
                    description=item["description"],
                    price=item["price"],
                    image_path=item["image_path"],
                    is_active=True,
                )
                db.add(product)
                db.flush()
            else:
                product.category_id = category.id
                product.name = item["name"]
                product.description = item["description"]
                product.price = item["price"]
                product.image_path = item["image_path"]
                product.is_active = True

            slot = db.scalar(
                select(MachineSlot).where(
                    MachineSlot.machine_id == machine.id,
                    MachineSlot.slot_code == item["slot_code"],
                )
            )
            if slot is None:
                slot = MachineSlot(
                    machine_id=machine.id,
                    slot_code=item["slot_code"],
                    slot_number=item["slot_number"],
                    product_id=product.id,
                motor_channel=item["motor_channel"],
                    capacity=item["capacity"],
                    is_active=True,
                )
                db.add(slot)
                db.flush()
            else:
                slot.product_id = product.id
                slot.motor_channel = item["motor_channel"]
                slot.capacity = item["capacity"]
                slot.is_active = True

            inventory = db.scalar(
                select(Inventory).where(Inventory.machine_slot_id == slot.id)
            )
            if inventory is None:
                inventory = Inventory(
                    machine_slot_id=slot.id,
                    quantity=item["quantity"],
                    reserved_quantity=0,
                )
                db.add(inventory)
            else:
                inventory.quantity = item["quantity"]
                inventory.reserved_quantity = 0

        db.commit()

    print("Seeded SMARTVEND-DEMO with 6 products, all in stock.")


if __name__ == "__main__":
    seed_demo_data()


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.admin_auth import router as admin_auth_router
from app.routers.categories import router as categories_router
from app.routers.health import router as health_router
from app.routers.inventory import router as inventory_router
from app.routers.inventory_movements import (
    router as inventory_movements_router,
)
from app.routers.mcu import router as mcu_router
from app.routers.machine_slots import router as machine_slots_router
from app.routers.machines import router as machines_router
from app.routers.orders import router as orders_router
from app.routers.payments import router as payments_router
from app.routers.products import router as products_router
from app.routers.store import router as store_router

app = FastAPI(
    title=settings.app_name,
    description="Backend system for the Smart Vending Machine.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([
        settings.frontend_origin.rstrip("/"),
        *(
            ["http://localhost:5173", "http://127.0.0.1:5173"]
            if settings.environment.lower() != "production"
            else []
        ),
    ])),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers.
app.include_router(health_router)
app.include_router(admin_auth_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(machines_router)
app.include_router(machine_slots_router)
app.include_router(orders_router)
app.include_router(inventory_router)
app.include_router(inventory_movements_router)
app.include_router(mcu_router)
app.include_router(payments_router)
app.include_router(store_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Smart Vending Machine API is running",
        "status": "online",
    }

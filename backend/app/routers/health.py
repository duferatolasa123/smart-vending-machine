from fastapi import APIRouter

from app.config import settings

router = APIRouter(
    prefix="/api/health",
    tags=["Health"],
)

@router.get("/")
def health_check():
    return {
        "status": "healthy",
        "application": settings.app_name,
        "environment": settings.environment,
    }
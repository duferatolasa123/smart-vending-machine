
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.categories import Category
from app.schemas.category import CategoryResponse


router = APIRouter(
    prefix="/api/categories",
    tags=["Categories"],
)


@router.get(
    "/",
    response_model=list[CategoryResponse],
)
def get_categories(
    db: Session = Depends(get_db),
) -> list[CategoryResponse]:
    """
    Retrieve all active product categories.
    This endpoint is publicly accessible to customers.
    """

    statement = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.name.asc())
    )

    categories = db.scalars(statement).all()

    return [
        CategoryResponse.model_validate(category)
        for category in categories
    ]

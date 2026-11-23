
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admins import Admin
from app.models.categories import Category
from app.models.products import Product
from app.schemas.product import ProductCreate, ProductResponse
from app.security.dependencies import get_current_admin


router = APIRouter(
    prefix="/api/products",
    tags=["Products"],
)


@router.get(
    "/",
    response_model=list[ProductResponse],
)
def get_products(
    category_id: UUID | None = Query(
        default=None,
        description="Filter products by category ID.",
    ),
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    """
    Retrieve all active products.

    Optionally filter products by category ID.
    This endpoint is publicly accessible to customers.
    """

    statement = select(Product).where(
        Product.is_active.is_(True)
    )

    if category_id is not None:
        statement = statement.where(
            Product.category_id == category_id
        )

    statement = statement.order_by(Product.name.asc())

    products = db.scalars(statement).all()

    return [
        ProductResponse.model_validate(product)
        for product in products
    ]


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> ProductResponse:
    """
    Create a new product.

    Requires an authenticated, active administrator.
    """

    category = db.scalar(
        select(Category).where(
            Category.id == product_data.category_id,
            Category.is_active.is_(True),
        )
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected category does not exist or is inactive.",
        )

    existing_product = db.scalar(
        select(Product).where(
            Product.sku == product_data.sku
        )
    )

    if existing_product is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists.",
        )

    product = Product(
        category_id=product_data.category_id,
        name=product_data.name.strip(),
        sku=product_data.sku.strip(),
        description=product_data.description,
        price=product_data.price,
        image_path=product_data.image_path,
        is_active=product_data.is_active,
    )

    try:
        db.add(product)
        db.commit()
        db.refresh(product)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The product could not be created because of a database conflict.",
        )

    return ProductResponse.model_validate(product)

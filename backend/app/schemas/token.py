
from pydantic import Field

from app.schemas.common import BaseSchema


class TokenResponse(BaseSchema):
    """Administrator authentication token returned after login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(gt=0)

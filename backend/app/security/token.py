
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import settings


def create_access_token(
    subject: UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed administrator access token."""

    now = datetime.now(UTC)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes
        )

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode an administrator access token."""

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={
                "require": ["sub", "iat", "exp", "type"],
            },
        )

        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type.")

        return cast(dict[str, Any], payload)

    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token.") from exc

"""Bounded keyset navigation using immutable creation time and UUID tie-breakers."""

import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_

from app.errors import fail


def page(
    db: Any,
    model: Any,
    query: Any,
    limit: int,
    offset: int,
    cursor: str | None,
    owner: UUID,
    scope: str,
) -> tuple[list[Any], str | None]:
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            if (
                set(value) != {"owner", "scope", "at", "id"}
                or value["owner"] != str(owner)
                or value["scope"] != scope
            ):
                raise ValueError
            at, identifier = datetime.fromisoformat(value["at"]), UUID(value["id"])
            if at.utcoffset() is None or offset:
                raise ValueError
        except (ValueError, TypeError, KeyError, UnicodeError):
            fail(
                422, "invalid_cursor", "Navigation expired or is invalid; return to the first page"
            )
        query = query.where(
            or_(model.created_at < at, and_(model.created_at == at, model.id < identifier))
        )
    rows = list(
        db.scalars(
            query.order_by(model.created_at.desc(), model.id.desc()).offset(offset).limit(limit + 1)
        )
    )
    following = None
    if len(rows) > limit:
        last = rows[limit - 1]
        following = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "owner": str(owner),
                        "scope": scope,
                        "at": last.created_at.isoformat(),
                        "id": str(last.id),
                    },
                    separators=(",", ":"),
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
    return rows[:limit], following

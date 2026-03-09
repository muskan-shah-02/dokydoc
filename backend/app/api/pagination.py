"""
Cursor-based pagination utilities for high-performance API endpoints.

Usage:
    from app.api.pagination import paginate_query, CursorPage

    @router.get("/items")
    def list_items(
        cursor: Optional[int] = Query(None),
        page_size: int = Query(50, le=200),
        db: Session = Depends(get_db),
    ):
        query = db.query(MyModel).filter(...)
        return paginate_query(query, MyModel.id, cursor=cursor, page_size=page_size)
"""
from typing import Any, Optional, Type, List
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy import Column, desc


def paginate_query(
    query: SAQuery,
    id_column: Column,
    *,
    cursor: Optional[int] = None,
    page_size: int = 50,
    direction: str = "desc",
) -> dict:
    """
    Apply cursor-based pagination to a SQLAlchemy query.

    Args:
        query: Base SQLAlchemy query
        id_column: The ID column to paginate on (must be indexed)
        cursor: The last ID from previous page (exclusive)
        page_size: Number of items per page
        direction: "desc" for newest-first, "asc" for oldest-first

    Returns:
        Dict with items, next_cursor, has_more
    """
    if direction == "desc":
        if cursor is not None:
            query = query.filter(id_column < cursor)
        query = query.order_by(desc(id_column))
    else:
        if cursor is not None:
            query = query.filter(id_column > cursor)
        query = query.order_by(id_column)

    # Fetch one extra to determine if there are more
    items = query.limit(page_size + 1).all()

    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]

    next_cursor = None
    if items and has_more:
        next_cursor = getattr(items[-1], id_column.key)

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "page_size": page_size,
    }

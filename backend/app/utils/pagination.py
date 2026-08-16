from typing import List, Optional, Tuple, Type

from sqlalchemy.orm import Query
from sqlalchemy import inspect


def apply_cursor_pagination(
    query: Query,
    model: Type,
    cursor: Optional[int] = None,
    limit: int = 20,
) -> Tuple[list, Optional[int], bool]:
    """
    通用游标分页：WHERE id > cursor ORDER BY id ASC LIMIT limit+1

    多取 1 条判断 has_more，避免额外 COUNT 查询。

    Args:
        query: SQLAlchemy 查询对象（已包含过滤条件）
        model: ORM 模型类（用于获取 id 列）
        cursor: 上一页最后一条记录的 ID，None 表示第一页
        limit: 每页数量

    Returns:
        (items, next_cursor, has_more)
    """
    if cursor is not None:
        query = query.filter(model.id > cursor)

    # 多取 1 条判断是否有下一页
    results = query.order_by(model.id.asc()).limit(limit + 1).all()

    has_more = len(results) > limit
    items = results[:limit]
    next_cursor = items[-1].id if has_more and items else None

    return items, next_cursor, has_more

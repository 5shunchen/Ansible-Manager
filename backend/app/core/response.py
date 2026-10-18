"""统一响应包裹：{code, message, data}；列表统一 {items, total, page, page_size}。"""
from typing import Any


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


def paginated(items: list, total: int, page: int, page_size: int) -> dict:
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})

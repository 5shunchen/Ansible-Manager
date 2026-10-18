"""轻量结构演进：SQLite 下幂等补齐 ORM 已声明但老库缺失的列。

开发期用 create_all 建表，但 create_all 不会给**已存在**的表加列；
模型新增字段后老库升级，查询会直接报缺列。
这里遍历 Base.metadata：表存在但缺列 → ALTER TABLE ADD COLUMN（带静态默认值，可离线补齐）。
（多版本正式演进仍由 alembic 负责。）
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base

logger = logging.getLogger(__name__)

# SQLite DDL：类型名 → 类型模板
_TYPE_DDL = {
    "BIGINT": "INTEGER", "INTEGER": "INTEGER", "SMALLINTEGER": "INTEGER",
    "BOOLEAN": "BOOLEAN", "DATETIME": "DATETIME", "TEXT": "TEXT", "JSON": "TEXT",
    "FLOAT": "REAL", "DOUBLE": "REAL",
}


def _column_ddl(col) -> str:
    name = col.type.__class__.__name__.upper()
    ddl = _TYPE_DDL.get(name, "TEXT")
    if ddl == "TEXT" and name == "VARCHAR":
        length = getattr(col.type, "length", None) or 255
        return f"VARCHAR({length})"
    if ddl == "TEXT" and name == "STRING":
        length = getattr(col.type, "length", None)
        return f"VARCHAR({length})" if length else "TEXT"
    return ddl


def _column_default(col) -> str:
    """ALTER ADD COLUMN 的静态默认值：server_default 映射为 CURRENT_TIMESTAMP，其余按类型。"""
    sd = col.server_default
    if sd is not None and getattr(sd, "arg", None) is not None and not callable(sd.arg):
        # func.now() / func.current_timestamp() → SQLite CURRENT_TIMESTAMP
        fname = getattr(sd.arg, "name", "") or ""
        if isinstance(fname, str) and fname.lower() in ("now", "current_timestamp", "sysdate", "localtimestamp"):
            return "CURRENT_TIMESTAMP"
    if col.nullable:
        return "NULL"
    name = col.type.__class__.__name__.upper()
    if name in ("BIGINT", "INTEGER", "SMALLINTEGER"):
        return "0"
    if name == "BOOLEAN":
        return "0"
    if name == "DATETIME":
        return "CURRENT_TIMESTAMP"
    return "''"


async def ensure_schema(engine: AsyncEngine) -> None:
    """按 ORM metadata 幂等补齐缺失列；表不存在时跳过（create_all 负责）。"""
    if engine.dialect.name != "sqlite":
        return
    async with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            rows = (await conn.execute(text(f"PRAGMA table_info({table.name})"))).fetchall()
            if not rows:
                continue
            existing = {r[1] for r in rows}
            for col in table.columns:
                if col.name in existing or col.primary_key:
                    continue
                ddl_type = _column_ddl(col)
                default = _column_default(col)
                await conn.execute(
                    text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl_type} DEFAULT {default}")
                )
                logger.info("结构补齐：%s.%s", table.name, col.name)

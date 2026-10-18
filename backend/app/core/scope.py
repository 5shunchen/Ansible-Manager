"""Agent 主机作用域：所有业务数据按「当前 Agent 主机」统一收窄。

作用域来自 HTTP 请求头 X-Agent-Host-Id，在鉴权依赖里写入 contextvar：
一个请求内后续所有业务查询都带上归属过滤，无需逐层改函数签名。

任务 worker / 调度器 / 监控采集等内部调用不携带请求头，作用域为 None（不过滤），
避免后台流程被前端上下文影响。
"""
from contextvars import ContextVar
from typing import Any, Optional

from sqlalchemy import and_

_current_agent_host_id: ContextVar[Optional[int]] = ContextVar("current_agent_host_id", default=None)


def set_scope(host_id: Optional[int]) -> None:
    _current_agent_host_id.set(host_id)


def get_scope() -> Optional[int]:
    return _current_agent_host_id.get()


def scope_conds(model: Any) -> list:
    """模型上的归属过滤条件；未选 Agent 主机或该模型无归属字段时返回空列表。"""
    hid = get_scope()
    col = getattr(model, "agent_host_id", None)
    if not hid or col is None:
        return []
    return [col == hid]


def scope_value() -> Optional[int]:
    """新建数据时的默认归属 Agent 主机。"""
    return get_scope()


def apply_scope(stmt: Any, model: Any) -> Any:
    """给 select 语句追加归属过滤；无作用域时原样返回。"""
    conds = scope_conds(model)
    if not conds:
        return stmt
    return stmt.where(and_(*conds))

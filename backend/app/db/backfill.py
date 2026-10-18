"""数据回填：历史数据归属到 Agent 主机。

Agent 主机就是 Ansible 控制机，业务数据都挂在它下面。加入作用域之前
已有的数据 agent_host_id 为空，统一归到第一台 Agent 主机（id 最小的
host_type='agent'）。幂等：已归属的数据不受影响；库里还没有 Agent 主机
时不做任何改动，等用户建好后再回填。
"""
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import DeployProject
from app.models.host import Host, HostGroup, Project
from app.models.task import Playbook, Task

logger = logging.getLogger(__name__)

# 需要归属的业务模型（Agent 主机自身是作用域根，排除在外）
_SCOPED_MODELS = [Project, Host, HostGroup, Playbook, Task, DeployProject]


async def first_agent_host_id(db: AsyncSession) -> int | None:
    """第一台 Agent 主机；库里没有则返回 None。"""
    stmt = select(Host.id).where(Host.host_type == "agent").order_by(Host.id).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def backfill_agent_scope(db: AsyncSession, agent_host_id: int | None = None) -> int:
    """把未归属的数据归到 Agent 主机，返回受影响行数。"""
    target = agent_host_id or await first_agent_host_id(db)
    if not target:
        return 0
    total = 0
    for model in _SCOPED_MODELS:
        conds = [model.agent_host_id.is_(None)]
        if model is Host:
            # Agent 主机自身是作用域根，归属保持为空
            conds.append(Host.host_type != "agent")
        res = await db.execute(update(model).where(*conds).values(agent_host_id=target))
        total += res.rowcount or 0
    if total:
        await db.commit()
        logger.info("历史数据归属到 Agent 主机 #%s：%s 行", target, total)
    return total

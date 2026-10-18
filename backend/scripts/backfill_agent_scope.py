"""把历史数据归属到 Agent 主机（幂等，可重复执行）。

正常情况下不需要手动跑：启动时以及新建第一台 Agent 主机时会自动回填。
这个脚本用于显式重跑或指定归属目标。

用法（在 backend 目录下）：
    python scripts/backfill_agent_scope.py                 # 自动选第一台 Agent 主机
    python scripts/backfill_agent_scope.py --agent-host-id 3   # 指定归属
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# 支持直接以脚本方式执行，并保证相对 sqlite 路径落在 backend 目录
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from app.db.backfill import backfill_agent_scope  # noqa: E402
from app.db.migrate import ensure_schema  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402


async def run(agent_host_id: int | None = None) -> int:
    # 老库可能还没补上归属列，先幂等补齐再回填
    await ensure_schema(engine)
    async with AsyncSessionLocal() as db:
        total = await backfill_agent_scope(db, agent_host_id)
    if total:
        print(f"已归属 {total} 行")
    else:
        print("没有需要归属的数据（库里可能还没有 Agent 主机，或数据都已归属）")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="把历史数据归属到 Agent 主机")
    parser.add_argument("--agent-host-id", type=int, default=None,
                        help="归属目标 Agent 主机 id；不传则取第一台（id 最小）的 Agent 主机")
    args = parser.parse_args()
    asyncio.run(run(args.agent_host_id))


if __name__ == "__main__":
    main()

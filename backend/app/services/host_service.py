"""主机域服务：项目/凭据/主机/主机组 + 连通检测。"""
from datetime import datetime, timezone
from app.core.time import now_cn
from pathlib import Path

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFoundError
from app.core.scope import apply_scope, scope_conds, scope_value
from app.core.security import decrypt_secret
from app.models.host import Host, HostGroup, Project, SshCredential
from app.models.system import SysAuditLog
from app.runner.interfaces import SshTarget
from app.schemas.host import (
    CredentialCreate, CredentialUpdate, HostCreate, HostGroupCreate, HostGroupUpdate,
    HostUpdate, ProjectCreate, ProjectUpdate,
)


def now() -> datetime:
    return now_cn()


# ---------- Project ----------
async def list_projects(db: AsyncSession) -> list[Project]:
    stmt = apply_scope(select(Project), Project).order_by(Project.id)
    return list((await db.execute(stmt)).scalars().all())


async def create_project(db: AsyncSession, req: ProjectCreate) -> Project:
    p = Project(**req.model_dump(), agent_host_id=scope_value())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_project(db: AsyncSession, pid: int, req: ProjectUpdate) -> Project:
    p = await db.get(Project, pid)
    if not p:
        raise NotFoundError("项目不存在")
    for f, v in req.model_dump(exclude_unset=True).items():
        setattr(p, f, v)
    await db.commit()
    await db.refresh(p)
    return p


async def delete_project(db: AsyncSession, pid: int) -> None:
    p = await db.get(Project, pid)
    if not p:
        raise NotFoundError("项目不存在")
    await db.delete(p)
    await db.commit()


# ---------- Credential ----------
async def list_credentials(db: AsyncSession) -> list[SshCredential]:
    return list((await db.execute(select(SshCredential).order_by(SshCredential.id))).scalars().all())


async def create_credential(db: AsyncSession, req: CredentialCreate, created_by: str = "") -> SshCredential:
    from app.core.security import encrypt_secret

    c = SshCredential(
        name=req.name, auth_type=req.auth_type, username=req.username,
        default_port=req.default_port, created_by=created_by,
        password_enc=encrypt_secret(req.password) if req.password else None,
        private_key_enc=encrypt_secret(req.private_key) if req.private_key else None,
        passphrase_enc=encrypt_secret(req.passphrase) if req.passphrase else None,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def update_credential(db: AsyncSession, cid: int, req: CredentialUpdate) -> SshCredential:
    from app.core.security import encrypt_secret

    c = await db.get(SshCredential, cid)
    if not c:
        raise NotFoundError("凭据不存在")
    if req.name is not None:
        c.name = req.name
    if req.username is not None:
        c.username = req.username
    if req.default_port is not None:
        c.default_port = req.default_port
    # 密文仅在显式传入时覆盖
    if req.password is not None:
        c.password_enc = encrypt_secret(req.password)
    if req.private_key is not None:
        c.private_key_enc = encrypt_secret(req.private_key)
    if req.passphrase is not None:
        c.passphrase_enc = encrypt_secret(req.passphrase)
    await db.commit()
    await db.refresh(c)
    return c


async def delete_credential(db: AsyncSession, cid: int) -> None:
    c = await db.get(SshCredential, cid)
    if not c:
        raise NotFoundError("凭据不存在")
    used = (await db.execute(select(Host.id).where(Host.credential_id == cid).limit(1))).scalar_one_or_none()
    if used:
        from app.core.exceptions import ConflictError

        raise ConflictError("凭据已被主机引用，无法删除")
    await db.delete(c)
    await db.commit()


async def build_ssh_target(db: AsyncSession, host: Host) -> SshTarget:
    """host + 解密凭据 → SshTarget（密文仅在内存短暂存在）。"""
    cred = await db.get(SshCredential, host.credential_id)
    if not cred:
        raise NotFoundError("主机凭据不存在")
    return SshTarget(
        ip=host.ip, port=host.port, username=cred.username,
        password=decrypt_secret(cred.password_enc) if cred.password_enc else None,
        private_key=decrypt_secret(cred.private_key_enc) if cred.private_key_enc else None,
        passphrase=decrypt_secret(cred.passphrase_enc) if cred.passphrase_enc else None,
    )


# ---------- Host ----------
async def list_hosts(
    db: AsyncSession, *, host_type: str | None = None, project_id: int | None = None,
    keyword: str | None = None, group_id: int | None = None,
    offset: int = 0, limit: int = 100,
) -> tuple[list[Host], int]:
    conditions = []
    if host_type:
        conditions.append(Host.host_type == host_type)
    # Agent 主机列表本身就是作用域维度，不收窄；其余主机按当前 Agent 主机收窄
    if host_type != "agent":
        conditions.extend(scope_conds(Host))
    if project_id:
        conditions.append(Host.project_id == project_id)
    if keyword:
        conditions.append((Host.hostname.like(f"%{keyword}%")) | (Host.ip.like(f"%{keyword}%")))
    if group_id:
        from app.models.host import HostGroupMember

        t = HostGroupMember.__table__
        in_group = select(t.c.host_id).where(t.c.group_id == group_id)
        conditions.append(Host.id.in_(in_group))

    stmt = select(Host)
    count_stmt = select(sa_func.count()).select_from(Host)
    if conditions:
        from sqlalchemy import and_

        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.order_by(Host.id).offset(offset).limit(limit))).scalars().unique().all()
    return list(rows), total


async def get_host(db: AsyncSession, host_id: int) -> Host:
    h = await db.get(Host, host_id)
    if not h:
        raise NotFoundError("主机不存在")
    return h


async def _resolve_credential(db: AsyncSession, req) -> SshCredential:
    """凭据解析：优先用已有 credential_id；否则按 主机+用户名+密码 自动建/更新密码凭据。"""
    from app.core.security import encrypt_secret

    if req.credential_id:
        cred = await db.get(SshCredential, req.credential_id)
        if not cred:
            raise NotFoundError("凭据不存在")
        return cred
    if not getattr(req, "ssh_password", None):
        raise ValidationAppError("请输入主机密码（或选择登录凭据）")
    name = f"{req.ip}:{req.port}/{req.ssh_username}"
    cred = (await db.execute(select(SshCredential).where(SshCredential.name == name))).scalar_one_or_none()
    if cred is None:
        cred = SshCredential(
            name=name, auth_type="password", username=req.ssh_username,
            default_port=req.port,
        )
        db.add(cred)
        await db.flush()
    cred.auth_type = "password"
    cred.username = req.ssh_username
    cred.default_port = req.port
    cred.password_enc = encrypt_secret(req.ssh_password)
    return cred


async def create_host(db: AsyncSession, req: HostCreate) -> Host:
    cred = await _resolve_credential(db, req)
    h = Host(
        hostname=req.hostname, ip=req.ip, port=req.port, host_type=req.host_type,
        project_id=req.project_id, credential_id=cred.id,
        description=req.description, tags=req.tags,
        # Agent 主机自身是作用域根，归属为空
        agent_host_id=None if req.host_type == "agent" else scope_value(),
        # Agent 主机专属 playbook 存放目录
        playbook_dir=req.playbook_dir if req.host_type == "agent" else None,
    )
    db.add(h)
    await db.flush()
    await _set_host_groups(db, h, req.group_ids)
    await db.commit()
    await db.refresh(h)
    if h.host_type == "agent":
        # 新建 Agent 主机时把此前无归属的历史数据归到它下面，否则这些数据会“看不见”
        from app.db.backfill import backfill_agent_scope
        from app.services.playbook_service import agent_playbook_root

        # 预建该 Agent 主机专属的 playbook 存放目录（data/playbooks/agent-{id}/）
        pb_root = await agent_playbook_root(h.id)
        pb_root.mkdir(parents=True, exist_ok=True)
        await backfill_agent_scope(db, h.id)

    # 建主机后自动跑一次连通检测，回填系统/CPU/内存（失败不阻断创建）
    await _auto_check_and_fill(db, h)
    return h


async def _auto_check_and_fill(db: AsyncSession, host: Host) -> None:
    """建主机后自动检测回填系统信息；SSH 不通时静默跳过（不阻断创建）。"""
    from app.runner.ssh.asyncssh_transport import AsyncSshTransport
    try:
        target = await build_ssh_target(db, host)
    except Exception:  # noqa: BLE001
        return
    transport = AsyncSshTransport(target)
    try:
        await check_host(db, host, transport)
    except Exception:  # noqa: BLE001
        pass


async def update_host(db: AsyncSession, host_id: int, req: HostUpdate) -> Host:
    from app.core.security import encrypt_secret

    h = await get_host(db, host_id)
    data = req.model_dump(exclude_unset=True)
    group_ids = data.pop("group_ids", None)
    ssh_password = data.pop("ssh_password", None)
    for f, v in data.items():
        setattr(h, f, v)
    if ssh_password:
        cred = await db.get(SshCredential, h.credential_id)
        if cred and cred.auth_type == "password":
            cred.password_enc = encrypt_secret(ssh_password)
    if group_ids is not None:
        await _set_host_groups(db, h, group_ids)
    await db.commit()
    await db.refresh(h)
    return h


async def delete_host(db: AsyncSession, host_id: int) -> None:
    h = await get_host(db, host_id)
    await db.delete(h)
    await db.commit()


async def _set_host_groups(db: AsyncSession, host: Host, group_ids: list[int]) -> None:
    """直接操作关联表，避免 async session 下的 ORM 集合懒加载。"""
    from sqlalchemy import delete, insert

    from app.models.host import HostGroupMember

    t = HostGroupMember.__table__
    await db.execute(delete(t).where(t.c.host_id == host.id))
    if group_ids:
        await db.execute(insert(t).values([
            {"host_id": host.id, "group_id": gid} for gid in group_ids
        ]))


async def check_host(db: AsyncSession, host: Host, transport) -> dict:
    """连通性检测：ping + 静态信息回填。transport 由调用方注入（可 mock）。"""
    try:
        await transport.connect()
    except Exception:  # noqa: BLE001 连接失败即为不可达
        await _mark_check(db, host, False)
        result = {"host_id": host.id, "reachable": False, "message": "连接失败"}
        try:
            await transport.close()
        except Exception:  # noqa: BLE001
            pass
        await db.commit()
        return result

    try:
        reachable = await transport.ping()
        result: dict = {"host_id": host.id, "reachable": reachable, "message": ""}
        if reachable:
            info = await transport.exec(
                "uname -s; uname -r; nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo;"
                " grep MemTotal /proc/meminfo", timeout=15,
            )
            if info.rc == 0:
                lines = [x.strip() for x in info.stdout.splitlines() if x.strip()]
                if len(lines) >= 4:
                    host.os_type, host.os_release = lines[0], lines[1]
                    try:
                        host.cpu_cores = int(lines[2])
                        host.mem_total_mb = int(lines[3].split()[1]) // 1024
                    except (ValueError, IndexError):
                        pass
                    result.update(os_type=host.os_type, os_release=host.os_release,
                                  cpu_cores=host.cpu_cores, mem_total_mb=host.mem_total_mb)
            host.status, host.fail_count, host.last_check_at = "online", 0, now()
            result["message"] = "连接成功"
        else:
            host.status = "offline"
            host.last_check_at = now()
            result["message"] = "连接失败"
        await db.commit()
        return result
    finally:
        await transport.close()


async def _mark_check(db: AsyncSession, host: Host, reachable: bool) -> None:
    host.status = "online" if reachable else "offline"
    host.last_check_at = now()


# 控制端 SSH 密钥对（持久化在 data/ 下，所有免密任务共用）
_KEY_PATH = Path(settings.data_dir) / "platform_ssh_key"


def _ensure_keypair() -> str:
    """确保控制端存在 SSH 密钥对，返回公钥内容。"""
    if not _KEY_PATH.with_suffix(".pub").exists():
        import subprocess

        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(_KEY_PATH), "-q"],
            check=True,
        )
    return _KEY_PATH.with_suffix(".pub").read_text().strip()


async def install_public_key(db: AsyncSession, host: Host, transport) -> dict:
    """把控制端公钥追加到目标机 ~/.ssh/authorized_keys（幂等）。"""
    public_key = _ensure_keypair()
    try:
        await transport.connect()
    except Exception as e:  # noqa: BLE001
        raise AppError(f"连接失败: {str(e)[:120]}")
    try:
        # 幂等：先检查公钥是否已存在
        check = await transport.exec("grep -qF '%s' ~/.ssh/authorized_keys 2>/dev/null" % public_key)
        if check.rc == 0:
            return {"host_id": host.id, "already": True, "message": "公钥已存在，免密已配置"}
        # 追加公钥（创建目录、设置权限）
        script = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            "touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
            "echo '%s' >> ~/.ssh/authorized_keys" % public_key
        )
        r = await transport.exec(script)
        if r.rc != 0:
            raise AppError(f"公钥写入失败: {r.stderr[:120]}")
        return {"host_id": host.id, "already": False, "message": "免密登录已配置"}
    finally:
        await transport.close()


# ---------- Agent 主机生命周期（安装 / 卸载 / 更新） ----------
# 系统当前可提供的最新 Agent 版本。升级 Agent 程序时提升此常量；
# 前端据此与数据库 agent_version 比较：只有 最新版 > 已装版 才显示「更新」按钮。
LATEST_AGENT_VERSION = "1.0.0"
AGENT_VERSION = LATEST_AGENT_VERSION


async def _agent_exec(host: Host, transport, script: str) -> None:
    """在 Agent 主机上执行生命周期命令，失败抛 AppError。"""
    try:
        await transport.connect()
    except Exception as e:  # noqa: BLE001
        raise AppError(f"连接失败: {str(e)[:120]}")
    try:
        r = await transport.exec(script)
        if r.rc != 0:
            raise AppError(f"命令执行失败: {(r.stderr or r.stdout)[:160]}")
    finally:
        await transport.close()


async def install_agent(db: AsyncSession, host: Host, transport) -> dict:
    """安装 Agent：在目标机部署 am-agent 运行环境（目录 + 版本标记 + 运行状态）。

    安装后该主机才成为"控制节点"：
      - 自身纳入定时采集（collector 只采已安装的 Agent 主机）
      - 名下被管主机才被允许调度与采集
      - 卸载后上述能力全部停用。
    """
    await _agent_exec(
        host, transport,
        "mkdir -p /opt/am-agent/bin /opt/am-agent/var && "
        "echo 'version=%s' > /opt/am-agent/info && "
        "echo running > /opt/am-agent/status" % AGENT_VERSION,
    )
    host.agent_status = "running"
    host.agent_version = AGENT_VERSION
    await db.commit()
    return {"host_id": host.id, "agent_status": host.agent_status, "message": "Agent 已安装并运行"}


async def uninstall_agent(db: AsyncSession, host: Host, transport) -> dict:
    """卸载 Agent：删除目标机 /opt/am-agent，置为 not_installed。"""
    await _agent_exec(
        host, transport,
        "rm -rf /opt/am-agent",
    )
    host.agent_status = "not_installed"
    host.agent_version = None
    await db.commit()
    return {"host_id": host.id, "agent_status": host.agent_status, "message": "Agent 已卸载"}


async def update_agent(db: AsyncSession, host: Host, transport) -> dict:
    """更新 Agent：把版本标记更新为最新，置为 running（模拟远程升级）。"""
    await _agent_exec(
        host, transport,
        "echo 'version=%s' > /opt/am-agent/info 2>/dev/null || echo 'version=%s' > /opt/am-agent/info"
        % (AGENT_VERSION, AGENT_VERSION),
    )
    host.agent_version = AGENT_VERSION
    host.agent_status = "running"
    await db.commit()
    return {"host_id": host.id, "agent_status": host.agent_status, "agent_version": host.agent_version,
            "message": "Agent 已更新"}


# ---------- HostGroup ----------
async def list_groups(db: AsyncSession) -> list[HostGroup]:
    stmt = apply_scope(select(HostGroup), HostGroup).order_by(HostGroup.id)
    return list((await db.execute(stmt)).scalars().all())


async def create_group(db: AsyncSession, req: HostGroupCreate) -> HostGroup:
    g = HostGroup(name=req.name, description=req.description, project_id=req.project_id,
                  vars=req.vars, agent_host_id=scope_value())
    db.add(g)
    await db.flush()
    if req.host_ids:
        hosts = list((await db.execute(select(Host).where(Host.id.in_(req.host_ids)))).scalars().all())
        g.hosts = hosts
    await db.commit()
    await db.refresh(g)
    return g


async def update_group(db: AsyncSession, gid: int, req: HostGroupUpdate) -> HostGroup:
    g = await db.get(HostGroup, gid)
    if not g:
        raise NotFoundError("主机组不存在")
    data = req.model_dump(exclude_unset=True)
    host_ids = data.pop("host_ids", None)
    for f, v in data.items():
        setattr(g, f, v)
    if host_ids is not None:
        hosts = list((await db.execute(select(Host).where(Host.id.in_(host_ids)))).scalars().all())
        g.hosts = hosts
    await db.commit()
    await db.refresh(g)
    return g


async def delete_group(db: AsyncSession, gid: int) -> None:
    g = await db.get(HostGroup, gid)
    if not g:
        raise NotFoundError("主机组不存在")
    await db.delete(g)
    await db.commit()


# ---------- Audit ----------
async def add_audit(
    db: AsyncSession, *, user_id: int | None, username: str, action: str,
    resource_type: str = "", resource_id: str = "", detail: dict | None = None,
    ip: str = "", success: bool = True,
) -> None:
    db.add(SysAuditLog(
        user_id=user_id, username=username, action=action, resource_type=resource_type,
        resource_id=str(resource_id), detail=detail, ip=ip, success=success,
    ))
    await db.commit()

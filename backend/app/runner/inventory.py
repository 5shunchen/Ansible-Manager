"""inventory 渲染：hosts/groups + 凭据 → ansible inventory 文本 + TaskSpec 组装。"""
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models.host import Host, HostGroup, SshCredential
from app.models.task import Playbook


def render_inventory(hosts: list[Host], creds: dict[int, SshCredential], groups: dict[int, HostGroup]) -> str:
    """渲染 ini inventory。密钥认证写 key 文件路径（由 prepare_task_dir 落盘），密码认证用 sshpass。"""
    lines: list[str] = []
    # 按主机组渲染；无组主机进 ungrouped
    grouped: dict[str, list[Host]] = {"ungrouped": []}
    for h in hosts:
        names = [g.name for g in h.groups if g.id in groups] or ["ungrouped"]
        for n in names:
            grouped.setdefault(n, []).append(h)

    for gname, ghosts in grouped.items():
        lines.append(f"[{gname}]")
        for h in ghosts:
            cred = creds[h.credential_id]
            parts = [f"{h.hostname} ansible_host={h.ip} ansible_port={h.port} ansible_user={cred.username}"]
            if cred.auth_type == "password":
                pw = decrypt_secret(cred.password_enc)
                parts.append(f"ansible_password='{pw}'")
            else:
                parts.append(f"ansible_ssh_private_key_file=env/ssh_key")
            lines.append(" ".join(parts))
        lines.append("")

    # 组级 vars
    for gid, g in groups.items():
        if g.vars:
            lines.append(f"[{g.name}:vars]")
            for k, v in g.vars.items():
                lines.append(f"{k}={v}")
            lines.append("")
    lines.append("[all:vars]")
    lines.append(f"ansible_python_interpreter={settings.ansible_python_interpreter}")
    return "\n".join(lines) + "\n"


async def prepare_task_dir(task_id: int, hosts: list[Host], playbook: Playbook | None,
                           playbook_content: str | None = None) -> str:
    """生成 data/tasks/{id}/private_data_dir：inventory/ + project/ + env/。"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import AsyncSessionLocal

    task_dir = Path(settings.task_dir) / str(task_id)
    inv_dir = task_dir / "inventory"
    env_dir = task_dir / "env"
    proj_dir = task_dir / "project"
    for d in (inv_dir, env_dir, proj_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 解析凭据与组
    async with AsyncSessionLocal() as db:
        cred_ids = {h.credential_id for h in hosts}
        from sqlalchemy import select

        creds = {c.id: c for c in (await db.execute(select(SshCredential).where(SshCredential.id.in_(cred_ids)))).scalars().all()}
        group_ids = {g.id for h in hosts for g in h.groups}
        groups = {g.id: g for g in (await db.execute(select(HostGroup).where(HostGroup.id.in_(group_ids)))).scalars().all()} if group_ids else {}

    (inv_dir / "hosts").write_text(render_inventory(hosts, creds, groups))

    # 让 ansible-runner 执行时能找到平台安装的 collection/role。
    # ansible-runner 会把 env/env 文件里的 KEY=VALUE 作为环境变量注入子进程；
    # 用 ANSIBLE_ROLES_PATH / ANSIBLE_COLLECTIONS_PATH 比 ansible.cfg 更可靠。
    collections_path = (settings.plugin_dir / "collections").resolve()
    roles_path = (settings.plugin_dir / "roles").resolve()
    env_file = (
        f"ANSIBLE_ROLES_PATH={roles_path}\n"
        f"ANSIBLE_COLLECTIONS_PATH={collections_path}\n"
        "ANSIBLE_HOST_KEY_CHECKING=False\n"
        "ANSIBLE_RETRY_FILES_ENABLED=False\n"
    )
    (env_dir / "env").write_text(env_file)

    # 私钥：任意一台使用密钥认证的凭据需要私钥文件（多凭据场景拼成多行发送文件，此处简化：写入每个任务用到的私钥）
    key_contents = []
    for c in creds.values():
        if c.auth_type == "private_key":
            sk = decrypt_secret(c.private_key_enc)
            if sk:
                key_contents.append(sk)
    if key_contents:
        key_file = env_dir / "ssh_key"
        key_file.write_text("\n".join(key_contents))
        key_file.chmod(0o600)

    # playbook：软链接到 data/playbooks/{id}/（部署任务则直接写渲染后的 playbook）
    if playbook_content is not None:
        (proj_dir / "site.yml").write_text(playbook_content)
    elif playbook is not None:
        (proj_dir / playbook.entry_file).parent.mkdir(parents=True, exist_ok=True)
        src = Path(playbook.disk_path) / playbook.entry_file
        if src.exists():
            dst = proj_dir / playbook.entry_file
            dst.write_text(src.read_text())
    return str(task_dir)

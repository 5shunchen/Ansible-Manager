"""containerd 部署编排：部署工程 CRUD → 渲染 playbook → 走任务管线 → 回写记录与容器当前态。"""
import shlex
import socket
from datetime import datetime, timezone
from app.core.time import now_cn
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.scope import apply_scope, get_scope, scope_value
from app.models.deployment import DeployContainer, DeployProject, DeployProjectHost, DeployRecord
from app.models.host import Host
from app.models.task import Task
from app.schemas.deployment import DeployActionRequest, DeployProjectCreate, DeployProjectUpdate

_TEMPLATES_DIR = Path(__file__).parent.parent / "runner" / "templates"


def now() -> datetime:
    return now_cn()


# ---------- CRUD ----------
async def list_projects(db: AsyncSession, keyword: str | None = None) -> list[DeployProject]:
    stmt = apply_scope(select(DeployProject), DeployProject)
    if keyword:
        stmt = stmt.where(DeployProject.name.like(f"%{keyword}%"))
    return list((await db.execute(stmt.order_by(DeployProject.id.desc()))).scalars().all())


async def get_project(db: AsyncSession, pid: int) -> DeployProject:
    p = await db.get(DeployProject, pid)
    if not p:
        raise NotFoundError("部署工程不存在")
    return p


async def create_project(db: AsyncSession, req: DeployProjectCreate, created_by: str = "") -> DeployProject:
    p = DeployProject(**{k: v for k, v in req.model_dump().items() if k != "hosts"},
                      created_by=created_by, agent_host_id=scope_value())
    db.add(p)
    await db.flush()
    await _set_hosts(db, p, req.hosts)
    await db.commit()
    await db.refresh(p)
    return p


async def update_project(db: AsyncSession, pid: int, req: DeployProjectUpdate) -> DeployProject:
    p = await get_project(db, pid)
    data = req.model_dump(exclude_unset=True)
    hosts = data.pop("hosts", None)
    for f, v in data.items():
        setattr(p, f, v)
    if hosts is not None:
        from app.schemas.deployment import DeployHostItem

        await _set_hosts(db, p, [DeployHostItem(**h) for h in hosts])
    await db.commit()
    await db.refresh(p)
    return p


async def delete_project(db: AsyncSession, pid: int) -> None:
    p = await get_project(db, pid)
    await db.delete(p)
    await db.commit()


async def _set_hosts(db: AsyncSession, p: DeployProject, hosts) -> None:
    existing = list((await db.execute(select(DeployProjectHost).where(
        DeployProjectHost.deploy_project_id == p.id))).scalars().all())
    for e in existing:
        await db.delete(e)
    await db.flush()
    for h in hosts:
        row = DeployProjectHost(
            deploy_project_id=p.id, host_id=h.host_id,
            container_name=h.container_name or _default_container_name(p, h.host_id),
            enabled=h.enabled,
        )
        db.add(row)


def _default_container_name(p: DeployProject, host_id: int) -> str:
    return p.code


# ---------- 部署动作 ----------
async def list_records(db: AsyncSession, deploy_project_id: int | None = None,
                       offset: int = 0, limit: int = 20) -> tuple[list[DeployRecord], int]:
    from sqlalchemy import func

    stmt = select(DeployRecord)
    count_stmt = select(func.count()).select_from(DeployRecord)
    if deploy_project_id:
        stmt = stmt.where(DeployRecord.deploy_project_id == deploy_project_id)
        count_stmt = count_stmt.where(DeployRecord.deploy_project_id == deploy_project_id)
    # 部署记录自身不带归属，按所属部署工程收窄
    scope = get_scope()
    if scope:
        proj_ids = select(DeployProject.id).where(DeployProject.agent_host_id == scope)
        stmt = stmt.where(DeployRecord.deploy_project_id.in_(proj_ids))
        count_stmt = count_stmt.where(DeployRecord.deploy_project_id.in_(proj_ids))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.order_by(DeployRecord.id.desc()).offset(offset).limit(limit))).scalars().all()
    return list(rows), total


def _render_playbook(p: DeployProject, image: str, container_name: str,
                     old_tag: str | None, host: DeployProjectHost,
                     cd_dir: str, cd_bundle: str, plain_http: bool,
                     tar_path: str = "") -> str:
    # 平台注入用 << >>，{{ }} 全部留给 Ansible 运行期（item/hc 等运行期变量写进 {{ }} 才对）
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True,
                      variable_start_string="<<", variable_end_string=">>")
    tpl = env.get_template("deploy_playbook.yml.j2")

    run_args: list[str] = []
    for k, v in (p.env or {}).items():
        run_args.append(f"-e {k}={v}")
    for host_p, guest in (p.ports or {}).items():
        run_args.append(f"-p {host_p}:{guest}")
    for host_m, guest in (p.mounts or {}).items():
        run_args.append(f"-v {host_m}:{guest}")
    for k, v in (p.labels or {}).items():
        run_args.append(f"--label {k}={v}")
    if p.network:
        run_args.append(f"--network {p.network}")
    if p.restart_policy:
        run_args.append(f"--restart {p.restart_policy}")

    bin_dir = f"{cd_dir}/bin"
    sock = f"{cd_dir}/run/containerd/containerd.sock"
    ctr_bin = f"{bin_dir}/am-ctr"          # 自带 ctr，重命名为 am-ctr，绝不撞系统 ctr
    daemon_bin = f"{bin_dir}/am-containerd"  # 自带 containerd，重命名为 am-containerd
    ns = p.namespace
    ph = "--plain-http " if plain_http else ""
    # 强制使用自定义 am-ctr（不用 nerdctl）
    ctl = f"{ctr_bin} --address {sock} -n {ns}"

    # 镜像来源：Docker 构建（build_type=docker，无论 build_host_id 是否设置）或 registry 拉取
    is_build = (p.build_type or "") == "docker"
    if is_build:
        cmd_pull = "true"
        cmd_import = f"{ctl} images import {tar_path}"
    else:
        cmd_pull = f"{ctl} images pull {ph}{image}".replace("  ", " ")
        cmd_import = "true"

    # 统一使用 am-ctr（不支持端口映射，需宿主网络时用 --net-host）
    cmd_rm_old = (f"{ctl} t kill {container_name} 2>/dev/null; {ctl} t rm {container_name} 2>/dev/null; "
                  f"{ctl} c rm {container_name} 2>/dev/null; true")
    ctr_args: list[str] = []
    for k, v in (p.env or {}).items():
        ctr_args.append(f"--env {k}={v}")
    for host_m, guest in (p.mounts or {}).items():
        ctr_args.append(f"--mount type=bind,src={host_m},dst={guest},options=rbind:rw")
    for k, v in (p.labels or {}).items():
        ctr_args.append(f"--label {k}={v}")
    if (getattr(p, "network", "") or "").lower() in ("host", "hostnet", "host_net"):
        ctr_args.append("--net-host")
    extra = (" " + " ".join(ctr_args)) if ctr_args else ""
    cmd_run = f"{ctl} run -d{extra} {image} {container_name}"
    cmd_rollback_rm = (f"{ctl} t kill {container_name} 2>/dev/null; {ctl} t rm {container_name} 2>/dev/null; "
                       f"{ctl} c rm {container_name} 2>/dev/null; true")
    cmd_rollback_run = (f"{ctl} run -d{extra} {image.split(':')[0]}:{old_tag} {container_name}"
                        if old_tag else "true")

    return tpl.render(
        image=image, cname=container_name, namespace=ns, runtime=p.runtime,
        healthcheck=p.healthcheck or {}, old_tag=old_tag or "",
        do_rollback="true" if p.rollback_enabled else "false",
        run_args=(" " + " ".join(run_args)) if run_args else "",
        cd_dir=cd_dir, cd_bin=bin_dir, cd_root=f"{cd_dir}/var/lib/containerd",
        cd_state=f"{cd_dir}/run/containerd", cd_sock=sock,
        cd_pid=f"{cd_dir}/run/containerd.pid", cd_log=f"{cd_dir}/containerd.log",
        cd_bundle=cd_bundle or "", cd_dirs=[bin_dir, f"{cd_dir}/var/lib/containerd", f"{cd_dir}/run/containerd"],
        # 挂载源可能不存在，运行期需先补建（否则 runc bind mount 失败）
        mount_dirs=list((p.mounts or {}).keys()),
        mount_dirs_shell=" ".join(shlex.quote(str(d)) for d in (p.mounts or {}).keys()),
        ctr_bin=ctr_bin, daemon_bin=daemon_bin,
        image_source="build" if is_build else "pull",
        tar_path=tar_path or "/tmp/am-image.tar",
        cmd_pull=cmd_pull, cmd_import=cmd_import, cmd_rm_old=cmd_rm_old, cmd_run=cmd_run,
        cmd_rollback_rm=cmd_rollback_rm, cmd_rollback_run=cmd_rollback_run,
    )


def _render_build_playbook(p: DeployProject, build_host: Host, image: str, tar_path: str) -> str:
    """Docker 构建阶段 play：只在构建主机上执行 build → save → fetch 回控制端。

    构建主机由 hosts 精确指定（hostname 作为 inventory 别名）。
    """
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True,
                      variable_start_string="<<", variable_end_string=">>")
    tpl = env.get_template("build_playbook.yml.j2")
    build_args = " ".join(f"--build-arg {k}={v}" for k, v in (p.build_args or {}).items())
    dockerfile = p.dockerfile or "Dockerfile"
    # 上下文已是绝对/相对路径，dockerfile 引用必须基于该上下文解析（ansible 执行目录不等于上下文）
    import os

    if not dockerfile.startswith("/"):
        dockerfile = os.path.join(p.build_context.rstrip("/"), dockerfile)
    return tpl.render(
        build_alias=build_host.hostname,
        image=image,
        tar_path=tar_path,
        dockerfile=dockerfile,
        build_args=f" {build_args}" if build_args else "",
        build_context=p.build_context,
    )
    """restart/stop/start 容器的 shell 片段：全部走隔离套件的自带二进制与 socket。

    stop: kill 任务并移除 task（保留镜像）；start/restart: 幂等地 kill+rm 后以当前镜像重新 run。
    """
    bin_dir = f"{cd_dir}/bin"
    sock = f"{cd_dir}/run/containerd/containerd.sock"
    path_env = f"PATH={bin_dir}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    # 统一使用自定义 am-ctr（不用 nerdctl）
    ctr = f"{bin_dir}/am-ctr --address {sock}"
    return {
        "stop": f"{ctr} t kill -s SIGTERM {container_name} 2>/dev/null; {ctr} t rm {container_name} 2>/dev/null; true",
        "start": f"env {path_env} {ctr} c rm {container_name} 2>/dev/null; {ctr} run -d {image} {container_name}",
        "restart": f"env {path_env} {ctr} t kill {container_name} 2>/dev/null; {ctr} t rm {container_name} 2>/dev/null; {ctr} c rm {container_name} 2>/dev/null; {ctr} run -d {image} {container_name}",
    }[action]


async def deploy(db: AsyncSession, pid: int, req: DeployActionRequest, username: str,
                 action: str = "deploy") -> DeployRecord:
    """deploy/rollback/restart/stop/start 统一入口。"""
    from app.services import task_service
    from app.services import config_service
    from app.runner.task_worker import task_worker

    p = await get_project(db, pid)
    # 隔离 containerd 套件：目标机安装目录 + 自带二进制 bundle（sys_config 热更新可覆盖）
    cd_dir = (await config_service.get(db, "deploy.containerd_dir")) or "/opt/am-containerd"
    cd_bundle = (await config_service.get(db, "deploy.containerd_bundle")) or ""
    plain_http = (await config_service.get(db, "deploy.registry_plain_http"))
    plain_http = str(plain_http).lower() not in ("false", "0", "no", "") if not isinstance(plain_http, bool) else plain_http
    host_rows = list((await db.execute(select(DeployProjectHost).where(
        DeployProjectHost.deploy_project_id == pid, DeployProjectHost.enabled.is_(True)))).scalars().all())
    if req.host_ids:
        host_rows = [h for h in host_rows if h.host_id in req.host_ids]
    if not host_rows:
        raise ValidationAppError("部署目标主机为空")

    # Docker 构建：在装有 Docker 服务的构建主机上 build + save，产物经控制端分发。
    # 未指定 build_host_id 时默认用「当前服务器」（ansible-manager 控制端本机）构建——
    # build play 落到 localhost（ansible 内置、local connection，无需进 inventory）。
    build_host = None
    control_hostname = socket.gethostname()
    is_build = bool((p.build_type or "") == "docker") and action in ("deploy",)
    if is_build:
        if not (p.build_context or "").strip():
            raise ValidationAppError("Docker 构建需要构建上下文路径")
        if p.build_host_id:
            build_host = await db.get(Host, p.build_host_id)
            if not build_host:
                raise ValidationAppError("构建主机不存在")
        else:
            # 当前服务器构建：build play 用 localhost（local connection）
            build_host = type("H", (), {"hostname": "localhost", "id": None})()

    if action == "rollback":
        tag = req.image_tag or None
        if not tag:
            raise ValidationAppError("回滚需要指定目标镜像 tag")
        old_tag = None
    else:
        tag = req.image_tag or p.default_tag
        old_tag = await _current_tags(db, pid, host_rows)

    image = f"{p.image_repo}:{tag}"
    registry_prefix = f"{p.registry_url}/" if p.registry_url and not p.image_repo.startswith(p.registry_url) else ""
    if registry_prefix:
        image = f"{registry_prefix}{image}"

    record = DeployRecord(
        deploy_project_id=pid, image_tag=tag or "", action=action, status="pending",
        from_tag=(old_tag or None) if action == "deploy" else None, triggered_by=username,
        started_at=now(),
    )
    db.add(record)
    await db.flush()

    # 镜像 tar 命名：部署工程 + tag，避免并发/多版本冲突
    safe_tag = "".join(c if c.isalnum() or c in ".-_" else "-" for c in (tag or "img"))
    tar_path = f"/tmp/am-deploy-{pid}-{safe_tag}.tar"

    # 为每个目标主机渲染一份 playbook（cname 可能不同），全部放进一个任务目录
    playbooks: list[str] = []
    if is_build:
        playbooks.append(_render_build_playbook(p, build_host, image, tar_path))
    for hr in host_rows:
        if action in ("restart", "stop", "start"):
            cmd = _lifecycle_cmd(action, p.runtime, hr.container_name, image, cd_dir)
            playbooks.append(f"""- hosts: all
  gather_facts: false
  vars:
    cd_dir: "{cd_dir}"
  tasks:
    - name: {action} 容器 {hr.container_name}（隔离 containerd 套件）
      ansible.builtin.shell: {cmd}
      args:
        executable: /bin/bash
      failed_when: false
""")
        else:
            # rollback/lifecycle 不重新构建，走 registry 或本地已有镜像
            playbooks.append(_render_playbook(p, image, hr.container_name, old_tag, hr, cd_dir, cd_bundle, plain_http, tar_path))

    task_name = f"[部署] {p.name} {action} {image}"
    task_host_ids = [h.host_id for h in host_rows]
    # 仅当构建主机是被登记的主机时才加入 inventory（当前服务器构建时 build_host 无 id）
    if is_build and getattr(build_host, "id", None) and build_host.id not in task_host_ids:
        task_host_ids.append(build_host.id)
    task = await task_service.create_task(
        db, None, triggered_by=username, task_type="deploy",
        playbook_id=None, name=task_name,
        host_ids=task_host_ids,
        deploy_record_id=record.id,
        # 渲染好的 playbook 随任务一次落库：worker 在 submit 后立即读取，不能事后补写
        playbook_content="\n".join(playbooks),
    )
    record.task_id = task.id
    await db.commit()
    # created_at 等由 DB server_default 生成，commit 后回读，避免响应模型校验缺字段
    await db.refresh(record)
    return record


async def _current_tags(db: AsyncSession, pid: int, host_rows) -> str | None:
    """当前部署 tag：经 deploy_project_host 关联查容器当前态（DeployContainer 无 deploy_project_id 字段）。"""
    host_ids = [hr.id for hr in host_rows if getattr(hr, "id", None)]
    if not host_ids:
        return None
    row = (await db.execute(select(DeployContainer).where(
        DeployContainer.deploy_project_host_id.in_(host_ids)).limit(1))).scalar_one_or_none()
    return row.current_tag if row and row.current_tag else None


async def on_task_finished(db: AsyncSession, task: Task) -> None:
    """任务终态联动部署记录与容器当前态。"""
    record = (await db.execute(select(DeployRecord).where(DeployRecord.task_id == task.id))).scalar_one_or_none()
    if not record:
        return
    record.status = task.status
    record.finished_at = task.finished_at
    record.stats = task.stats
    if task.status == "success" and record.action in ("deploy", "rollback"):
        # 更新容器当前态
        host_links = list((await db.execute(select(DeployProjectHost).where(
            DeployProjectHost.deploy_project_id == record.deploy_project_id,
            DeployProjectHost.enabled.is_(True)))).scalars().all())
        if record.action == "deploy":
            for hr in host_links:
                c = (await db.execute(select(DeployContainer).where(
                    DeployContainer.deploy_project_host_id == hr.id))).scalar_one_or_none()
                if c is None:
                    c = DeployContainer(deploy_project_host_id=hr.id, container_name=hr.container_name)
                    db.add(c)
                c.current_tag = record.image_tag
                c.status = "running"
                c.deployed_at = now()
    # 部署失败自动回滚到旧版本（rollback_enabled=true 时）
    if task.status == "failed" and record.action == "deploy" and record.from_tag:
        try:
            await deploy(db, record.deploy_project_id,
                         DeployActionRequest(image_tag=record.from_tag), "system",
                         action="rollback")
        except Exception:  # noqa: BLE001
            pass
    await db.commit()

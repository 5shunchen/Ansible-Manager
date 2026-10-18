"""执行抽象层 Protocol：services 依赖此接口而非实现，测试注入 Fake。

SSHTransport  —— 采集/Web终端/文件管理共用
TaskExecutor  —— ansible-runner 封装，任务提交/取消
"""
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


@dataclass
class CommandResult:
    rc: int
    stdout: str
    stderr: str = ""


@dataclass
class SshTarget:
    """连接目标（由 host + 解密后的凭据组装，不落库不外传）。"""

    ip: str
    port: int = 22
    username: str = "root"
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    connect_timeout: int = 10


EventCallback = Callable[[dict], None]


@runtime_checkable
class SSHTransport(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def exec(self, cmd: str, timeout: float = 15) -> CommandResult: ...
    async def ping(self) -> bool: ...


@dataclass
class TaskSpec:
    """一次任务执行的完整输入（渲染好的 inventory 路径、playbook 入口、变量）。"""

    task_id: int
    private_data_dir: str
    playbook_entry: str
    extra_vars: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 3600
    play_name: str = "run"


class RunningHandle(Protocol):
    def cancel(self) -> None: ...
    def kill(self) -> None: ...
    @property
    def done(self) -> bool: ...


@runtime_checkable
class TaskExecutor(Protocol):
    """submit 同步执行（在线程池中运行），通过 on_event 流式回调，返回最终状态。"""

    def run(self, spec: TaskSpec, on_event: EventCallback) -> tuple[str, int]:
        ...


class TransportFactory(Protocol):
    """按 SshTarget 产出 transport 实例的工厂。"""

    def __call__(self, target: SshTarget) -> SSHTransport: ...

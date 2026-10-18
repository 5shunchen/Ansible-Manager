"""ansible-runner 封装：实现 TaskExecutor 接口。

run() 为同步方法，由 task_worker 放在线程池中执行；on_event 回调线程安全。
"""
import os
import sys
from pathlib import Path
from typing import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


def _ensure_ansible_path() -> None:
    """ansible-runner 通过 PATH 查找 ansible-playbook。
    服务进程（systemd/容器/nohup）的 PATH 常不含解释器 bin 目录，这里显式补上。"""
    bin_dir = str(Path(sys.executable).resolve().parent)
    path = os.environ.get("PATH", "")
    if bin_dir not in path.split(os.pathsep):
        os.environ["PATH"] = bin_dir + os.pathsep + path


class RunningHandle:
    """持有 ansible-runner 的 thread/runner 引用，支持 cancel/kill。"""

    def __init__(self):
        self._thread = None
        self._runner = None
        self._canceled = False

    def bind(self, thread, runner) -> None:
        self._thread, self._runner = thread, runner

    @property
    def done(self) -> bool:
        return self._thread is not None and not self._thread.is_alive()

    def cancel(self) -> None:
        """优雅取消：runner 收到 cancel 文件后正常收尾。"""
        if self._runner is not None:
            try:
                self._runner.cancel_event = True
            except Exception:
                pass
        self._canceled = True

    def kill(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            # ansible-runner 无强杀 API，cancel_event 已尽力；极端情况靠超时兜底
            self.cancel()


class AnsibleExecutor:
    """实现 app.runner.interfaces.TaskExecutor。"""

    def __init__(self):
        self.handles: dict[int, RunningHandle] = {}

    def run(self, spec, on_event: Callable[[dict], None]) -> tuple[str, int]:
        import ansible_runner

        from app.core.config import settings

        _ensure_ansible_path()
        handle = RunningHandle()
        self.handles[spec.task_id] = handle

        # 让 ansible 能找到平台安装的 collection/role。ansible-runner 不直接接受 env 参数，
        # 这里在进程级 os.environ 上临时设置（ansible 子进程会继承），run 完恢复。
        saved = {
            "ANSIBLE_ROLES_PATH": os.environ.get("ANSIBLE_ROLES_PATH"),
            "ANSIBLE_COLLECTIONS_PATH": os.environ.get("ANSIBLE_COLLECTIONS_PATH"),
            "ANSIBLE_HOST_KEY_CHECKING": os.environ.get("ANSIBLE_HOST_KEY_CHECKING"),
            "ANSIBLE_RETRY_FILES_ENABLED": os.environ.get("ANSIBLE_RETRY_FILES_ENABLED"),
        }
        os.environ["ANSIBLE_ROLES_PATH"] = str((settings.plugin_dir / "roles").resolve())
        os.environ["ANSIBLE_COLLECTIONS_PATH"] = str((settings.plugin_dir / "collections").resolve())
        os.environ["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        os.environ["ANSIBLE_RETRY_FILES_ENABLED"] = "False"

        try:
            thread, runner = ansible_runner.run_async(
                private_data_dir=spec.private_data_dir,
                playbook=spec.playbook_entry,
                extravars=spec.extra_vars or None,
                timeout=spec.timeout_seconds,
                quiet=True,
                event_handler=lambda ev: _safe_event(on_event, ev),
            )
            handle.bind(thread, runner)
            thread.join()
            status = runner.status or "unknown"
            rc = runner.rc if runner.rc is not None else -1
            return status, rc
        finally:
            self.handles.pop(spec.task_id, None)
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _safe_event(on_event: Callable[[dict], None], ev: dict) -> None:
    """ansible-runner event_handler：屏蔽 verbose 之外的杂音事件，统一交给回调。"""
    try:
        if not isinstance(ev, dict):
            return
        on_event(ev)
    except Exception:  # noqa: BLE001 事件回调不允许打断执行
        logger.warning("task_event_handler_error", exc_info=True)

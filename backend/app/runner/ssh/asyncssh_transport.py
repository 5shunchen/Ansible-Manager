"""asyncssh 实现的 SSHTransport：采集 exec / 终端 shell / SFTP 共用连接。"""
import asyncio
from typing import Optional

import asyncssh

from app.core.exceptions import SSHConnectError
from app.core.logging import get_logger
from app.runner.interfaces import CommandResult, SshTarget

logger = get_logger(__name__)


class AsyncSshTransport:
    """单主机 SSH 会话。async with 用法或显式 connect/close。"""

    def __init__(self, target: SshTarget):
        self.target = target
        self._conn: Optional[asyncssh.SSHClientConnection] = None

    @property
    def conn(self) -> asyncssh.SSHClientConnection:
        if self._conn is None or self._conn.is_closed():
            raise SSHConnectError(f"SSH 连接未建立或已关闭: {self.target.ip}:{self.target.port}")
        return self._conn

    async def connect(self) -> None:
        kwargs: dict = {
            "host": self.target.ip,
            "port": self.target.port,
            "username": self.target.username,
            "known_hosts": None,  # 运维平台内部环境，跳过 host key 校验
            "connect_timeout": self.target.connect_timeout,
            # 关闭一切交互/转发类请求：不申请 x11 转发、不申请 agent 转发、不起 sftp 子系统
            # 避免目标机 sshd 日志里出现 x11 forwarding 之类的转发请求
            "x11_forwarding": False,
            "agent_forwarding": False,
        }
        if self.target.private_key:
            kwargs["client_keys"] = [asyncssh.import_private_key(self.target.private_key)]
        elif self.target.password:
            kwargs["password"] = self.target.password
        else:
            raise SSHConnectError("凭据缺少密码或私钥")
        try:
            self._conn = await asyncssh.connect(**kwargs)
        except (OSError, asyncssh.Error, ValueError) as e:
            raise SSHConnectError(f"SSH 连接失败 {self.target.ip}:{self.target.port}: {e}") from e

    async def close(self) -> None:
        if self._conn and not self._conn.is_closed():
            self._conn.close()

    async def exec(self, cmd: str, timeout: float = 15) -> CommandResult:
        try:
            result = await asyncio.wait_for(self.conn.run(cmd), timeout=timeout + 5)
        except asyncio.TimeoutError as e:
            raise SSHConnectError(f"命令执行超时 {self.target.ip}: {timeout}s") from e
        except (OSError, asyncssh.Error) as e:
            raise SSHConnectError(f"命令执行失败 {self.target.ip}: {e}") from e
        return CommandResult(rc=result.exit_status or 0, stdout=result.stdout or "", stderr=result.stderr or "")

    async def ping(self) -> bool:
        try:
            result = await self.exec("echo ok", timeout=8)
            return result.rc == 0 and "ok" in result.stdout
        except Exception:
            return False

    # ---- 供 Web 终端 / SFTP 使用 ----
    async def open_shell(self, cols: int = 80, rows: int = 24):
        """开交互式 PTY shell：返回包装对象，提供 readline/write/resize/close。"""
        stdin_w, stdout_r, _stderr_r = await self.conn.open_session(
            term_type="xterm-256color",
            term_size=(cols, rows),
            command="bash -i",
            x11_forwarding=False,
        )

        class _Pty:
            """PTY 通道适配器：把 asyncssh 流接口包装成 channel 风格 read/write/resize。"""

            def read_stream(self):
                return stdout_r.__aiter__()

            async def read(self, n=65536):
                return await stdout_r.read(n)

            async def readline(self):
                return await stdout_r.readline()

            def write(self, data):
                stdin_w.write(data)

            async def change_pty(self, cols=80, rows=24):
                # 通过 stdin_w.channel 拿到底层 SSHClientChannel，调 change_terminal_size 同步 PTY 尺寸
                try:
                    chan = getattr(stdin_w, "channel", None)
                    if chan is not None:
                        chan.change_terminal_size(cols, rows)
                except Exception:  # noqa: BLE001
                    pass

            async def close(self):
                try:
                    stdin_w.write_eof()
                except Exception:  # noqa: BLE001
                    pass

        return _Pty()

    def sftp(self):
        return self.conn.start_sftp_client()


def transport_factory(target: SshTarget) -> AsyncSshTransport:
    return AsyncSshTransport(target)

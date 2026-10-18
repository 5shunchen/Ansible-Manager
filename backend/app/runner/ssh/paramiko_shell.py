"""基于 paramiko 的交互式 PTY shell 通道（Web 终端专用）。

paramiko 的 invoke_shell 是业界最成熟的交互式 shell 实现，
read/write/resize 语义清晰，比 asyncssh 流接口稳定得多。
"""
import paramiko


class ParamikoPtyShell:
    """对 paramiko invoke_shell 的轻封装，提供 read/write/resize/close。"""

    def __init__(self, channel):
        self._ch = channel

    def read_sync(self, size: int = 4096) -> bytes:
        """同步读（供 run_in_executor 调用）：读到可用数据即返回。"""
        import time
        if self._ch.recv_ready():
            return self._ch.recv(size)
        return b""  # 没数据立即返回（reader 会 sleep 再循环）

    def is_closed(self) -> bool:
        return self._ch.exit_status_ready()

    def write(self, data: str) -> None:
        self._ch.send(data)

    async def resize(self, cols: int = 80, rows: int = 24) -> None:
        self._ch.resize_pty(width=cols, height=rows)

    async def close(self) -> None:
        try:
            self._ch.close()
        except Exception:  # noqa: BLE001
            pass


async def open_paramiko_shell(host: str, port: int, username: str, password: str,
                              cols: int = 80, rows: int = 24) -> ParamikoPtyShell:
    """建立 paramiko 连接并开交互式 PTY shell。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=username, password=password, timeout=10)
    channel = client.invoke_shell(term="xterm-256color", width=cols, height=rows)
    channel.settimeout(0)  # 非阻塞 recv
    shell = ParamikoPtyShell(channel)
    shell._client = client  # 持有 client，close 时一起关
    return shell

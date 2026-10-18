"""测试替身：FakeTransport（回放固定 /proc 输出）、FakeExecutor（回放事件序列）。"""
from app.runner.interfaces import CommandResult


FAKE_COLLECT_OUTPUT = """===STAT1===
cpu  100 200 300 4000 500 0 0 0 0 0
===STAT2===
cpu  110 210 310 4100 510 0 0 0 0 0
===LOAD===
0.52 0.58 0.60 1/500 12345
===MEM===
MemTotal:       8000000 kB
MemAvailable:   4000000 kB
SwapTotal:      2000000 kB
SwapFree:       2000000 kB
===DISK===
Filesystem     1024-blocks      Used Available Capacity Mounted on
/dev/sda1        50000000  25000000  25000000      50% /
/dev/sdb1        10000000   9000000   1000000      90% /data
===NET===
  eth0: 1000000 100 0 0 0 0 0 0 500000 100
  lo: 100 0 0 0 0 0 0 0 100 0
===UP===
123456.78 234567.89
===DONE===
"""


class FakeTransport:
    """替换 asyncssh transport；exec 返回预置输出。"""

    def __init__(self, target=None, outputs: dict[str, str] | None = None):
        self.target = target
        self.outputs = outputs or {}
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        if self.target and self.target.password == "__fail__":
            raise ConnectionError("simulated connect failure")
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def exec(self, cmd: str, timeout: float = 15) -> CommandResult:
        for key, out in self.outputs.items():
            if key in cmd:
                return CommandResult(rc=0, stdout=out)
        if "grep '^cpu '" in cmd or "===STAT1===" in cmd:
            return CommandResult(rc=0, stdout=FAKE_COLLECT_OUTPUT)
        if "uname" in cmd:
            return CommandResult(rc=0, stdout="Linux\n3.10.0\n4\nMemTotal:       8000000 kB")
        if "echo ok" in cmd:
            return CommandResult(rc=0, stdout="ok")
        return CommandResult(rc=0, stdout="")

    async def ping(self) -> bool:
        try:
            await self.connect()
            r = await self.exec("echo ok")
            return r.rc == 0
        except Exception:  # noqa: BLE001
            return False


class FakeExecutor:
    """回放固定事件序列的 TaskExecutor。"""

    def __init__(self, events: list[dict] | None = None, final=("successful", 0)):
        self.events = events or [
            {"event": "playbook_on_start", "event_data": {"name": "fake play"}, "stdout": "PLAY [fake]"},
            {"event": "runner_on_start", "event_data": {"host": "h1", "task": "ping", "task_action": "ping"}},
            {"event": "runner_on_ok", "event_data": {"host": "h1", "task": "ping", "res": {"msg": "pong"}}, "stdout": "ok"},
            {"event": "playbook_on_stats", "event_data": {}, "stdout": "PLAY RECAP"},
        ]
        self.final = final
        self.spec = None
        self.on_event = None

    def run(self, spec, on_event):
        self.spec, self.on_event = spec, on_event
        for ev in self.events:
            on_event(ev)
        return self.final

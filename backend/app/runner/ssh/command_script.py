"""远端指标采集脚本：一次 SSH 往返拿全部指标，===X=== 分段，零远端依赖。"""

COLLECT_SCRIPT = r"""
echo "===STAT1==="
grep '^cpu ' /proc/stat
sleep 1
echo "===STAT2==="
grep '^cpu ' /proc/stat
echo "===LOAD==="
cat /proc/loadavg
echo "===MEM==="
grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
echo "===DISK==="
df -kP 2>/dev/null | grep -v -E 'tmpfs|devtmpfs'
echo "===NET==="
cat /proc/net/dev
echo "===UP==="
cat /proc/uptime
echo "===DONE==="
"""

# 采集脚本需要的静态信息（首次连通时执行一次）
PROBE_SCRIPT = (
    "uname -s; uname -r; nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo;"
    " grep MemTotal /proc/meminfo"
)


def _cpu_times(line: str) -> list[float]:
    # cpu  user nice system idle iowait irq softirq steal ...
    parts = line.split()[1:]
    return [float(x) for x in parts] + [0.0] * (10 - len(parts))


def parse_metric_sections(stdout: str) -> dict:
    """分段解析远端输出 → 指标 dict（纯函数，单测核心）。"""
    sections: dict[str, list[str]] = {}
    current = None
    for line in stdout.splitlines():
        if line.startswith("===") and line.endswith("==="):
            current = line.strip("= ")
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)

    if not sections.get("STAT1") or not sections.get("STAT2"):
        raise ValueError("采集输出缺少 CPU 数据段")

    t1 = _cpu_times(sections["STAT1"][0])
    t2 = _cpu_times(sections["STAT2"][0])
    d = [b - a for a, b in zip(t1, t2)]
    total = sum(d)
    cpu_usage = cpu_user = cpu_sys = cpu_iowait = None
    if total > 0:
        idle = d[3] + (d[4] if len(d) > 4 else 0)
        cpu_usage = round((total - idle) / total * 100, 2)
        cpu_user = round(d[0] / total * 100, 2)
        cpu_sys = round(d[2] / total * 100, 2)
        cpu_iowait = round((d[4] / total * 100) if len(d) > 4 else 0.0, 2)

    load = {}
    if sections.get("LOAD"):
        parts = sections["LOAD"][0].split()
        if len(parts) >= 3:
            load = {"load1": float(parts[0]), "load5": float(parts[1]), "load15": float(parts[2])}

    mem = {}
    for line in sections.get("MEM", []):
        parts = line.split()
        if len(parts) >= 2:
            mem[parts[0].rstrip(":")] = int(parts[1]) // 1024  # kB → MB
    mem_total = mem.get("MemTotal", 0)
    mem_avail = mem.get("MemAvailable", 0)
    mem_used = mem_total - mem_avail
    mem_pct = round(mem_used / mem_total * 100, 2) if mem_total else None
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    swap_pct = round((swap_total - swap_free) / swap_total * 100, 2) if swap_total else 0.0

    # 磁盘：每挂载点一行（Filesystem blocks Used Available Capacity Mounted），找根分区
    disks = []
    root_pct = None
    for line in sections.get("DISK", []):
        parts = line.split()
        if len(parts) < 6 or not parts[5].startswith("/"):
            continue
        try:
            total_mb = int(parts[1]) // 1024
            used_mb = int(parts[2]) // 1024
            pct = int(parts[4].rstrip("%"))
        except ValueError:
            continue
        disks.append({"mount": parts[5], "device": parts[0], "total_mb": total_mb, "used_mb": used_mb, "used_pct": pct})
        if parts[5] == "/":
            root_pct = pct

    uptime_s = None
    if sections.get("UP"):
        try:
            uptime_s = int(float(sections["UP"][0].split()[0]))
        except (ValueError, IndexError):
            pass

    return {
        "cpu_usage": cpu_usage, "cpu_user": cpu_user, "cpu_sys": cpu_sys, "cpu_iowait": cpu_iowait,
        **load,
        "mem_total_mb": mem_total, "mem_used_mb": mem_used, "mem_used_pct": mem_pct,
        "swap_total_mb": swap_total, "swap_used_pct": swap_pct,
        "disk_root_used_pct": root_pct,
        "net_rx_kbps": None, "net_tx_kbps": None,  # 单次快照无差分，采集器跨周期计算
        "uptime_s": uptime_s,
        "disks": disks,
    }

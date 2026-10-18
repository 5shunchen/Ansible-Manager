"""纯函数单测：采集脚本解析。"""
import pytest

from app.runner.ssh.command_script import parse_metric_sections
from app.tests.fakes import FAKE_COLLECT_OUTPUT


def test_parse_cpu():
    s = parse_metric_sections(FAKE_COLLECT_OUTPUT)
    # delta: user=10 nice=10 system=10 idle=100 iowait=10，total=140
    # 空闲 = idle + iowait = 110 → busy 30/140 ≈ 21.43
    assert s["cpu_usage"] == pytest.approx(21.43, abs=0.2)
    assert s["cpu_user"] == pytest.approx(10 / 140 * 100, abs=0.2)
    assert s["cpu_iowait"] == pytest.approx(10 / 140 * 100, abs=0.2)


def test_parse_mem_load_disk():
    s = parse_metric_sections(FAKE_COLLECT_OUTPUT)
    assert s["mem_total_mb"] == 8000000 // 1024  # kB → MB
    assert s["mem_used_pct"] is not None and 0 < s["mem_used_pct"] < 100
    assert s["load1"] == 0.52
    assert s["disk_root_used_pct"] == 50
    mounts = {d["mount"] for d in s["disks"]}
    assert mounts == {"/", "/data"}
    assert s["uptime_s"] == 123456


def test_parse_missing_stat_raises():
    with pytest.raises(ValueError):
        parse_metric_sections("===LOAD===\n1 2 3\n")

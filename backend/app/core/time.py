"""时间工具：统一东八区（北京时间），存库与展示一致。"""
from datetime import datetime, timedelta, timezone


def now_cn() -> datetime:
    """东八区当前时间（naive，不带 tzinfo，直接可入库）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)

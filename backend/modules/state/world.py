"""Application-wide world fields, independent of character-authored schemas."""

from datetime import date, time
import re


def parse_date(value: object) -> date:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("世界.日期 必须采用 YYYY-MM-DD 格式")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("世界.日期 必须是真实有效的日期（YYYY-MM-DD）") from None


def validate_world(content: dict) -> dict:
    world = content.get("世界")
    if not isinstance(world, dict):
        raise ValueError("世界 必须存在且为对象")
    parse_date(world.get("日期"))
    if world.get("星期") not in ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"):
        raise ValueError("世界.星期 必须为星期一至星期六或星期日")
    clock = world.get("时间")
    if not isinstance(clock, str) or re.fullmatch(r"[0-9]{2}:[0-9]{2}", clock) is None:
        raise ValueError("世界.时间 必须采用 24 小时制 HH:mm 格式")
    try:
        time.fromisoformat(clock)
    except ValueError:
        raise ValueError("世界.时间 必须是有效时间（00:00 至 23:59）") from None
    if not isinstance(world.get("地点"), str):
        raise ValueError("世界.地点 必须存在且为字符串，允许为空")
    return content

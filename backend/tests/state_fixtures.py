"""Valid world data for tests that do not exercise character-specific schemas."""

WORLD = {"日期": "2026-10-19", "星期": "星期一", "时间": "08:00", "地点": ""}
STATE_SCHEMA = '''
from pydantic import BaseModel, Field
class Schema(BaseModel):
    世界: dict = Field(default_factory=lambda: {"日期": "2026-10-19", "星期": "星期一", "时间": "08:00", "地点": ""})
'''

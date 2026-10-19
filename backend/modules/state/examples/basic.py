"""Editable state_schema example. Rename fields and adjust validators as needed."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StateNode(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class WorldState(StateNode):
    日期: str = "2026-10-19"
    星期: str = "星期一"
    时间: str = "08:00"
    地点: str = "未知"


class CharacterState(StateNode):
    好感度: int = 0
    关系: str = "陌生"
    想法: str = ""

    @field_validator("好感度")
    @classmethod
    def clamp_affinity(cls, value):
        return max(0, min(100, value))

    @model_validator(mode="after")
    def correct_relationship(self):
        if self.好感度 < 100 and self.关系 == "恋人":
            self.关系 = "朋友"
        return self


class Schema(StateNode):
    世界: WorldState = Field(default_factory=WorldState)
    角色: CharacterState = Field(default_factory=CharacterState)

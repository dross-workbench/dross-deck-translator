from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Segment(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1500)


class TranslateRequest(StrictModel):
    segments: list[Segment] = Field(min_length=1, max_length=24)
    context: list[str] = Field(default_factory=list, max_length=6)
    source_language: Literal["ja"] = "ja"
    target_language: Literal["en"] = "en"
    game_id: str = Field(default="unknown", max_length=120)
    model_identity: str | None = Field(default=None, max_length=200)


class AnalysisRequest(StrictModel):
    text: str = Field(min_length=1, max_length=1500)
    translation: str = Field(default="", max_length=3000)
    context: list[str] = Field(default_factory=list, max_length=6)
    explain: bool = False

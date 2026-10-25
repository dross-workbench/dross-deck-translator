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


class VocabularyRequest(StrictModel):
    event_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9-]+$')
    word: str = Field(min_length=1, max_length=100)
    dictionary_form: str = Field(min_length=1, max_length=100)
    reading: str = Field(default='', max_length=150)
    meaning: str = Field(default='', max_length=3000)
    sentence: str = Field(min_length=1, max_length=1500)
    sentence_translation: str = Field(default='', max_length=3000)
    game_id: str = Field(default='unknown', max_length=120)
    game_title: str = Field(default='', max_length=200)

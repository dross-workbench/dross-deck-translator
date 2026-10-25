import os
from dataclasses import dataclass
from pathlib import Path

# Explicit local models only. Cloud aliases and arbitrary model URLs are rejected.
LOCAL_MODELS = {"translategemma:4b", "qwen3:4b", "qwen3:1.7b", "qwen3:0.6b"}


@dataclass
class Config:
    token: str
    translation_model: str = "qwen3:4b"
    analysis_model: str = "qwen3:4b"
    data_dir: Path = Path(".local/data")
    timeout: float = 120
    keep_alive: str = "30s"
    allow_images: bool = False
    anki_enabled: bool = False

    def __post_init__(self):
        if len(self.token) < 32:
            raise ValueError("Set DROSS_TOKEN to a random token of at least 32 characters")
        if {self.translation_model, self.analysis_model} - LOCAL_MODELS:
            raise ValueError("Only explicitly supported local Ollama models are allowed")
        self.data_dir = Path(self.data_dir)

    @classmethod
    def from_env(cls):
        return cls(
            token=os.environ.get("DROSS_TOKEN", ""),
            translation_model=os.environ.get("DROSS_TRANSLATION_MODEL", "qwen3:4b"),
            analysis_model=os.environ.get("DROSS_ANALYSIS_MODEL", "qwen3:4b"),
            data_dir=Path(os.environ.get("DROSS_DATA_DIR", ".local/data")),
            timeout=float(os.environ.get("DROSS_TIMEOUT", "120")),
            keep_alive=os.environ.get("DROSS_KEEP_ALIVE", "30s"),
            allow_images=os.environ.get("DROSS_ALLOW_IMAGES") == "1",
            anki_enabled=os.environ.get("DROSS_ANKI_ENABLED") == "1",
        )

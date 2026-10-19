"""Project-local defaults; no implicit network backends."""
from dataclasses import dataclass, field
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / 'local' / 'settings.toml'


@dataclass
class Settings:
    model: str = str(Path.home() / '.local/share/voxtype/models/ggml-base.bin')
    voxtype: str = '/usr/lib/voxtype/voxtype-vulkan'
    language: str = 'auto'
    vocabulary: list[str] = field(default_factory=lambda: ['Talky', 'Omarchy', 'Hyprland', 'Voxtype'])
    cleanup: bool = True
    cleanup_timeout: float = 2.5
    eager: bool = False
    max_recording_seconds: int = 120
    asr_timeout: float = 90.0
    formatter_model: str = str(ROOT / 'models/qwen2.5-1.5b-instruct-q4_k_m.gguf')
    formatter_binary: str = ''

    @classmethod
    def load(cls, path=None):
        file = Path(path) if path else DEFAULT_CONFIG
        values = tomllib.loads(file.read_text()) if file.exists() else {}
        result = cls(**values)
        if result.language not in ('auto', 'en', 'de'):
            raise ValueError('language must be auto, en, or de')
        if not 0 < result.cleanup_timeout <= 30 or not 1 <= result.max_recording_seconds <= 600:
            raise ValueError('invalid timeout')
        if not isinstance(result.vocabulary, list) or any(not isinstance(x, str) for x in result.vocabulary):
            raise ValueError('vocabulary must be a list of strings')
        return result

import json
import os
import threading
from pathlib import Path

from pydantic import ValidationError

from tts_service.models import VoiceConfig

DEFAULT_CONFIG_PATH = os.environ.get(
    "CONFIG_PATH",
    str(Path(__file__).parent.parent.parent / "config" / "voice_config.json"),
)

_current_config: VoiceConfig | None = None
_config_lock = threading.RLock()


class ConfigLoadError(Exception):
    pass


class ConfigReloadError(Exception):
    pass


def load_config(path: str) -> VoiceConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(f"invalid JSON: {exc}") from exc

    try:
        return VoiceConfig(**data)
    except ValidationError as exc:
        raise ConfigLoadError(f"schema validation failed: {exc}") from exc


def get_current_config() -> VoiceConfig:
    global _current_config
    with _config_lock:
        if _current_config is None:
            _current_config = load_config(DEFAULT_CONFIG_PATH)
        return _current_config


def reload_config() -> VoiceConfig:
    global _current_config
    with _config_lock:
        try:
            new_config = load_config(DEFAULT_CONFIG_PATH)
            _current_config = new_config
            return new_config
        except Exception as exc:
            raise ConfigReloadError(str(exc)) from exc

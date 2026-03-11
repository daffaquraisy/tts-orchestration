import json
import threading
import pytest

from tts_service.config import (
    ConfigLoadError,
    ConfigReloadError,
    load_config,
    reload_config,
    get_current_config,
)
import tts_service.config as config_module
from tts_service.models import VoiceConfig


def _valid_payload():
    return {
        "rules": [
            {"condition": "contains_question", "voice_id": "v1", "rate": 145, "volume": 0.9, "pitch": 5},
        ],
        "default_rule": {"condition": "default", "voice_id": "v2", "rate": 150, "volume": 0.9, "pitch": 0},
    }


def test_load_valid_config(tmp_path):
    cfg_file = tmp_path / "voice_config.json"
    cfg_file.write_text(json.dumps(_valid_payload()))

    result = load_config(str(cfg_file))

    assert isinstance(result, VoiceConfig)
    assert len(result.rules) == 1
    assert result.default_rule is not None


def test_load_invalid_json_raises(tmp_path):
    cfg_file = tmp_path / "bad.json"
    cfg_file.write_text("{not valid json}")

    with pytest.raises(ConfigLoadError):
        load_config(str(cfg_file))


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.json")


def test_reload_config_reflects_changes(tmp_path, monkeypatch):
    cfg_file = tmp_path / "voice_config.json"
    payload = _valid_payload()
    cfg_file.write_text(json.dumps(payload))

    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_module, "_current_config", None)

    first = reload_config()
    assert first.rules[0].rate == 145

    payload["rules"][0]["rate"] = 200
    cfg_file.write_text(json.dumps(payload))

    second = reload_config()
    assert second.rules[0].rate == 200


def test_reload_config_invalid_file_keeps_old(tmp_path, monkeypatch):
    cfg_file = tmp_path / "voice_config.json"
    cfg_file.write_text(json.dumps(_valid_payload()))

    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_module, "_current_config", None)

    good = reload_config()
    assert good is not None

    cfg_file.write_text("{broken")

    with pytest.raises(ConfigReloadError):
        reload_config()

    # old config still intact
    assert config_module._current_config is not None
    assert config_module._current_config.default_rule is not None


def test_config_is_thread_safe(tmp_path, monkeypatch):
    cfg_file = tmp_path / "voice_config.json"
    cfg_file.write_text(json.dumps(_valid_payload()))

    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_module, "_current_config", None)

    errors = []
    results = []

    def read():
        try:
            results.append(get_current_config())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=read) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(results) == 10
    assert all(isinstance(r, VoiceConfig) for r in results)

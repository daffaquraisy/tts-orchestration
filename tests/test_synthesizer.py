import os
import pytest
from unittest.mock import MagicMock, patch

from tts_service.models import VoiceRule
from tts_service.synthesizer import SynthesisError, synthesize


@pytest.fixture
def default_rule():
    return VoiceRule(condition="default", voice_id="english_male_1", rate=150, volume=0.9, pitch=0)


def _make_engine_mock(output_path_holder: list):
    """Returns a mock pyttsx3 engine that creates a real file when save_to_file is called."""
    mock_engine = MagicMock()

    def fake_save(text, path):
        output_path_holder.append(path)
        with open(path, "wb") as f:
            f.write(b"RIFF....fake wav data")

    mock_engine.save_to_file.side_effect = fake_save
    mock_engine.getProperty.return_value = []
    return mock_engine


def test_synthesize_returns_audio_file_path(tmp_path, default_rule, monkeypatch):
    holder = []
    mock_engine = _make_engine_mock(holder)

    with patch("tts_service.synthesizer.pyttsx3.init", return_value=mock_engine):
        monkeypatch.setenv("AUDIO_OUTPUT_DIR", str(tmp_path))
        path = synthesize("Hello world", default_rule)

    assert os.path.exists(path)
    assert path.endswith(".wav")


def test_synthesize_applies_rate(tmp_path, monkeypatch):
    rule = VoiceRule(condition="default", voice_id="v1", rate=200, volume=0.9, pitch=0)
    holder = []
    mock_engine = _make_engine_mock(holder)

    with patch("tts_service.synthesizer.pyttsx3.init", return_value=mock_engine):
        monkeypatch.setenv("AUDIO_OUTPUT_DIR", str(tmp_path))
        synthesize("test", rule)

    mock_engine.setProperty.assert_any_call("rate", 200)


def test_synthesize_applies_volume(tmp_path, monkeypatch):
    rule = VoiceRule(condition="default", voice_id="v1", rate=150, volume=0.5, pitch=0)
    holder = []
    mock_engine = _make_engine_mock(holder)

    with patch("tts_service.synthesizer.pyttsx3.init", return_value=mock_engine):
        monkeypatch.setenv("AUDIO_OUTPUT_DIR", str(tmp_path))
        synthesize("test", rule)

    mock_engine.setProperty.assert_any_call("volume", 0.5)


def test_synthesize_empty_text_raises(default_rule):
    with pytest.raises(SynthesisError):
        synthesize("", default_rule)


def test_output_file_is_written(tmp_path, default_rule, monkeypatch):
    holder = []
    mock_engine = _make_engine_mock(holder)

    with patch("tts_service.synthesizer.pyttsx3.init", return_value=mock_engine):
        monkeypatch.setenv("AUDIO_OUTPUT_DIR", str(tmp_path))
        path = synthesize("Test audio output", default_rule)

    assert os.path.getsize(path) > 0


def test_synthesize_cleanup_on_failure(tmp_path, default_rule, monkeypatch):
    mock_engine = MagicMock()
    mock_engine.getProperty.return_value = []
    mock_engine.save_to_file.side_effect = RuntimeError("engine exploded")

    with patch("tts_service.synthesizer.pyttsx3.init", return_value=mock_engine):
        monkeypatch.setenv("AUDIO_OUTPUT_DIR", str(tmp_path))
        with pytest.raises(SynthesisError):
            synthesize("Test", default_rule)

    wav_files = list(tmp_path.glob("*.wav"))
    assert len(wav_files) == 0

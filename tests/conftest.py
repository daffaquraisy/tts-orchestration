import pytest
import fakeredis
from fastapi.testclient import TestClient

from tts_service.models import VoiceConfig, VoiceRule


@pytest.fixture
def sample_config() -> VoiceConfig:
    return VoiceConfig(
        rules=[
            VoiceRule(condition="contains_question", voice_id="english_female_1", rate=145, volume=0.9, pitch=5),
            VoiceRule(condition="is_exclamatory", voice_id="english_male_1", rate=170, volume=1.0, pitch=10),
            VoiceRule(condition="is_formal", voice_id="english_male_2", rate=130, volume=0.85, pitch=0),
        ],
        default_rule=VoiceRule(condition="default", voice_id="english_male_1", rate=150, volume=0.9, pitch=0),
    )


@pytest.fixture
def sample_text_formal() -> str:
    return "Dear Sir, I am writing to formally request your assistance."


@pytest.fixture
def sample_text_question() -> str:
    return "What time does the meeting start?"


@pytest.fixture
def sample_text_exclamatory() -> str:
    return "This is amazing! We did it!"


@pytest.fixture
def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server)
    yield client
    client.flushall()


@pytest.fixture
def test_app(fake_redis, monkeypatch):
    import tts_service.main as main_module

    monkeypatch.setattr(main_module, "_redis", fake_redis)
    monkeypatch.setattr(main_module, "_queue", None)

    from tts_service.main import app
    return TestClient(app)

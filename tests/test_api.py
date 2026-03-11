import json
import pytest
import fakeredis
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import tts_service.main as main_module
from tts_service.main import app


@pytest.fixture(autouse=True)
def reset_singletons():
    main_module._redis = None
    main_module._queue = None
    yield
    main_module._redis = None
    main_module._queue = None


@pytest.fixture
def fake_redis():
    server = fakeredis.FakeServer()
    r = fakeredis.FakeRedis(server=server, decode_responses=False)
    return r


@pytest.fixture
def client(fake_redis, monkeypatch):
    monkeypatch.setattr(main_module, "_redis", fake_redis)

    mock_queue = MagicMock()
    monkeypatch.setattr(main_module, "_queue", mock_queue)

    return TestClient(app)


def test_post_synthesize_returns_job_id(client):
    resp = client.post("/synthesize", json={"text": "Hello world"})
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    # basic UUID shape check
    assert len(data["job_id"]) == 36


def test_post_synthesize_empty_text_returns_422(client):
    resp = client.post("/synthesize", json={"text": ""})
    assert resp.status_code == 422


def test_post_synthesize_missing_body_returns_422(client):
    resp = client.post("/synthesize", json={})
    assert resp.status_code == 422


def test_get_status_queued_job(client, fake_redis):
    resp = client.post("/synthesize", json={"text": "Hello"})
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/status/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in ("queued", "processing", "done")


def test_get_status_unknown_job_returns_404(client):
    resp = client.get("/status/totally-made-up-job-id")
    assert resp.status_code == 404


def test_post_reload_config_returns_200(client, tmp_path, monkeypatch):
    import json as _json
    import tts_service.config as config_module

    cfg_file = tmp_path / "voice_config.json"
    cfg_file.write_text(_json.dumps({
        "rules": [
            {"condition": "contains_question", "voice_id": "v1", "rate": 145, "volume": 0.9, "pitch": 5}
        ],
        "default_rule": {"condition": "default", "voice_id": "v2", "rate": 150, "volume": 0.9, "pitch": 0},
    }))

    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_module, "_current_config", None)

    resp = client.post("/reload-config")
    assert resp.status_code == 200
    assert resp.json()["reloaded"] is True


def test_post_reload_config_invalid_file_returns_500(client, tmp_path, monkeypatch):
    import tts_service.config as config_module

    cfg_file = tmp_path / "bad.json"
    cfg_file.write_text("{broken json}")

    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_module, "_current_config", None)

    resp = client.post("/reload-config")
    assert resp.status_code == 500
    assert "error" in resp.json()


def test_get_status_done_job_has_audio_path(client, fake_redis):
    job_id = "test-done-job-id"
    fake_redis.set(
        f"job:{job_id}",
        json.dumps({"job_id": job_id, "status": "done", "audio_path": "/tmp/tts_abc123.wav"}),
    )

    resp = client.get(f"/status/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["audio_path"] is not None

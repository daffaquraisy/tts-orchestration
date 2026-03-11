import json
import os
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis import Redis

from tts_service.config import ConfigReloadError, reload_config
from tts_service.models import SynthesisJob, SynthesisRequest

app = FastAPI(title="TTS Orchestration Service")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

_redis: Redis | None = None
_queue = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL)
    return _redis


def get_queue():
    global _queue
    if _queue is None:
        from rq import Queue  # lazy — rq uses fork which breaks on Windows at import time
        _queue = Queue(connection=get_redis())
    return _queue


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/synthesize", status_code=202)
def synthesize(body: SynthesisRequest):
    job_id = str(uuid.uuid4())
    r = get_redis()
    q = get_queue()

    r.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "queued"}))

    # import here to avoid circular imports at module level
    from tts_service.worker import process_tts_job

    q.enqueue(
        process_tts_job,
        job_id,
        body.text,
        REDIS_URL,
        job_id=job_id,
    )

    return SynthesisJob(job_id=job_id, status="queued")


@app.get("/status/{job_id}")
def status(job_id: str):
    r = get_redis()
    raw = r.get(f"job:{job_id}")
    if raw is None:
        return JSONResponse(status_code=404, content={"detail": "job not found"})

    data = json.loads(raw)
    return SynthesisJob(
        job_id=data["job_id"],
        status=data["status"],
        audio_path=data.get("audio_path"),
        error=data.get("error"),
    )


@app.post("/reload-config")
def reload():
    try:
        cfg = reload_config()
        return {"reloaded": True, "rule_count": len(cfg.rules)}
    except ConfigReloadError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})

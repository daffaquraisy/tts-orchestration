import json

from redis import Redis

from tts_service.analyzer import analyze_text
from tts_service.config import get_current_config
from tts_service.models import SynthesisResult
from tts_service.router import route_voice
from tts_service.synthesizer import SynthesisError, synthesize


def process_tts_job(job_id: str, text: str, redis_url: str = "redis://localhost:6379") -> dict:
    r = Redis.from_url(redis_url)

    r.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "processing"}))

    try:
        config = get_current_config()
        analysis = analyze_text(text)
        rule = route_voice(analysis, config)
        audio_path = synthesize(text, rule)

        result = SynthesisResult(
            job_id=job_id,
            audio_path=audio_path,
            voice_id=rule.voice_id,
            rate=rule.rate,
            analysis=analysis,
        )

        r.set(
            f"job:{job_id}",
            json.dumps({
                "job_id": job_id,
                "status": "done",
                "audio_path": audio_path,
                "result": result.model_dump(),
            }),
        )
        return result.model_dump()

    except SynthesisError as exc:
        r.set(
            f"job:{job_id}",
            json.dumps({"job_id": job_id, "status": "failed", "error": str(exc)}),
        )
        raise

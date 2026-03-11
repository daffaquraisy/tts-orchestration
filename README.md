# Dynamic TTS Orchestration Service

> Question 1 — Take-home submission

---

## Mandatory Declaration

I confirm that this submission was completed without the assistance of any AI-based coding or generation tools.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + uvicorn | async-ready, Pydantic validation built-in, minimal boilerplate |
| TTS engine | pyttsx3 + espeak-ng | open-source, no network dependency, runs fully on CPU |
| Queue | Redis + RQ | simple job queue with built-in status tracking, no broker config overhead |
| Config | JSON + threading.RLock | hot-reloadable at runtime without restart, human-editable |
| Models | Pydantic v2 | strict validation, auto-generates 422 on bad input |
| Runtime | Python 3.13 + uv | fast dependency resolution, reproducible installs |
| Deploy | Docker Compose | single command to bring up redis + api + worker |

---

## Architecture

The full architecture diagram (component topology, request lifecycle, step-by-step pipeline) is in [`../index.html`](../index.html). Open it in a browser.

Three diagrams are included:
- **System Overview** — component boundaries and data flow
- **Request Flow** — async sequence from POST to audio file
- **Step-by-Step** — detailed pipeline breakdown

The TDD and pseudocode that drove implementation is in [`../tts_tdd_pseudocode.md`](../tts_tdd_pseudocode.md).

---

## How it works

```
POST /synthesize
  → Pydantic validates (empty text → 422, no business logic hit)
  → uuid4 job_id generated
  → status=queued written to Redis
  → job enqueued to RQ
  → 202 returned immediately (non-blocking)

RQ Worker (separate process/container):
  → dequeues job, writes status=processing
  → analyze_text()   — rule-based: checks ?, !, formal keywords
  → route_voice()    — iterates config rules, first match wins
  → synthesize()     — espeak-ng writes .wav to shared volume
  → writes status=done + audio_path to Redis

GET /status/{job_id}
  → reads from Redis, returns current state

POST /reload-config
  → reloads voice_config.json under RLock (thread-safe)
  → old config stays active if new file is invalid (no downtime)
```

---

## Project structure

```
tts-service/
├── pyproject.toml
├── Dockerfile            # API image
├── Dockerfile.worker     # RQ worker image
├── docker-compose.yml
├── config/
│   └── voice_config.json
├── src/
│   └── tts_service/
│       ├── models.py       # Pydantic models
│       ├── config.py       # thread-safe config loader + hot-reload
│       ├── analyzer.py     # rule-based text analysis
│       ├── router.py       # voice routing logic
│       ├── synthesizer.py  # pyttsx3 / espeak-ng wrapper
│       ├── worker.py       # RQ task
│       └── main.py         # FastAPI app
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_analyzer.py
    ├── test_router.py
    ├── test_synthesizer.py
    └── test_api.py
```

---

## Setup and running

### Option A — Docker (recommended)

**Prerequisites:** Docker Desktop (or Docker Engine + Compose plugin)

```bash
git clone <repo>

# Build images and start all services (redis + api + worker + rq-dashboard)
docker compose up --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| RQ Dashboard | http://localhost:9181 |

Verify the stack is healthy:

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

**Scale workers horizontally:**
```bash
docker compose up --scale worker=3
```

**Copy a generated audio file out of the container:**
```bash
# get the audio_path from GET /status/<job_id>, then:
docker compose cp worker:/tmp/tts_output/<filename>.wav ./output.wav
```

**Stop everything:**
```bash
docker compose down
```

---

### Option B — Local dev (no Docker)

**Prerequisites:**

- Python 3.13
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `curl -Lsf https://astral.sh/uv/install.sh | sh`)
- Redis running locally (`redis-server` or via Docker: `docker run -p 6379:6379 redis`)
- `espeak-ng` installed on the system:
  - Ubuntu/Debian: `sudo apt install espeak-ng`
  - macOS: `brew install espeak-ng`

```bash
# Install all dependencies (including dev)
uv sync

# Terminal 1 — run the API
uv run uvicorn tts_service.main:app --reload --port 8000

# Terminal 2 — run the RQ worker
REDIS_URL=redis://localhost:6379 uv run rq worker --url redis://localhost:6379

# (optional) Terminal 3 — RQ dashboard
uv run rq-dashboard --redis-url redis://localhost:6379
```

**Environment variables (local dev defaults):**

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `CONFIG_PATH` | `config/voice_config.json` | Path to voice config file |
| `AUDIO_OUTPUT_DIR` | system temp dir | Directory where `.wav` files are written |

---

## Running tests

```bash
# Install deps (if not done already)
uv sync

# Run all tests
uv run pytest tests/ -v --tb=short
```

Tests are fully isolated — `fakeredis` for Redis, `unittest.mock` for pyttsx3. No real Redis or audio hardware needed.

```
35 passed in 0.26s
```

---

## API

### `POST /synthesize`
Submit text for synthesis. Returns immediately with a job ID.

```bash
curl -s -X POST http://localhost:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "What time does the meeting start?"}'
# → {"job_id": "...", "status": "queued"}
```

### `GET /status/{job_id}`
Poll job state. Transitions: `queued → processing → done | failed`

```bash
curl http://localhost:8000/status/<job_id>
# → {"job_id": "...", "status": "done", "audio_path": "/tmp/tts_output/tts_abc.wav"}
```

### `POST /reload-config`
Hot-reload `voice_config.json` without restarting anything.

```bash
curl -X POST http://localhost:8000/reload-config
# → {"reloaded": true, "rule_count": 3}
```

If the new file is invalid JSON or fails Pydantic validation, returns 500 and keeps the previous config active.

---

## Voice routing

Rules are evaluated in JSON order — first match wins. Configured in `config/voice_config.json`, reloadable at runtime.

| Condition | Detection | Default voice | Rate |
|---|---|---|---|
| `contains_question` | `?` present | en+m3 | 145 wpm |
| `is_exclamatory` | `!` present | en+f5 | 170 wpm |
| `is_formal` | formal keywords (dear, formally, sincerely…) | en+f3 | 100 wpm |
| `default` | none of the above | en | 150 wpm |

To change routing without redeploying: edit `config/voice_config.json`, then `POST /reload-config`.

---

## Design decisions

**Non-blocking by design.** `POST /synthesize` returns 202 immediately. Audio synthesis is CPU-bound and can take seconds — blocking the HTTP response would kill throughput under any real load. RQ offloads this to a worker process entirely.

**Config hot-reload under RLock.** The config is a global singleton protected by `threading.RLock`. Workers call `get_current_config()` per job — not cached at job dispatch time — so a reload takes effect on the next job without any restart. If the reload fails, the old config stays active. No downtime window.

**Rule order = priority.** Voice routing iterates `config.rules` in JSON array order. First match wins. This means priority is controlled entirely by file order, not code. An ops person can reprioritize routing by reordering JSON and hitting `/reload-config`. No redeploy.

**pyttsx3 + espeak-ng subprocess fallback.** pyttsx3's espeak driver only accepts voices from its registered list. The espeak-ng `+variant` notation (e.g. `en+f3`, `en+m3`) is standard espeak CLI syntax but gets silently dropped when passed through pyttsx3's C API. The synthesizer detects the `+` and routes those calls directly to the `espeak-ng` subprocess instead, which handles variants correctly.

**CPU only, no GPU.** espeak-ng is a formant-based synthesizer — deterministic, fast, and runs fine on any CPU. For this use case (rule-based routing, no ML) GPU adds zero value. The tradeoff is audio quality versus operational simplicity. espeak-ng is not going to sound like a neural TTS model, but it's fully open-source, ships in a Docker image with no cloud dependency, and synthesizes in milliseconds.

**Shared volume for audio.** The API container and worker container share a Docker volume (`tts_audio`). The worker writes the `.wav` file there and stores the path in Redis. The API can then serve or expose that path without having to shuttle audio bytes through Redis (which would be a bad idea — Redis isn't a file store).

---

## Trade-offs

| Decision | Upside | Downside |
|---|---|---|
| RQ over Celery | much simpler setup, zero config | fewer features (no chaining, no canvas), less battle-tested at scale |
| pyttsx3 over direct espeak-ng | Python-native API, easier to mock in tests | thin wrapper with edge cases (voice variants, headless environments) |
| JSON config over DB/env vars | human-readable, hot-reloadable, version-controllable | no audit trail, no access control, concurrent writes not protected |
| In-memory config singleton | zero latency reads | config state is per-process — worker and API maintain independent copies |
| Rule-based analysis only | deterministic, no model loading, instant | crude — misses tone, sarcasm, context; "dear" in casual text still triggers formal |

---

## Limitations

- **espeak-ng audio quality** is robotic by design. It's a formant synthesizer, not a neural model. Good enough for demos and rule validation, not production TTS.
- **Text analysis is naive.** Keyword matching for formality. "I formally request you shut up" and a business letter both trigger `is_formal`. No context window.
- **Audio files accumulate.** There's no cleanup job. `/tmp/tts_output` grows indefinitely. Production would need a TTL-based cleanup or object storage (S3 + presigned URLs).
- **Worker config state is independent.** If you run 3 workers and call `/reload-config`, only the API process reloads. Workers pick up config on the next job start via `get_current_config()`, so they converge eventually but not atomically. A proper fix would use a Redis pub/sub reload signal broadcast to all workers.
- **No authentication.** All endpoints are open. Fine for internal tooling, not for anything internet-facing.
- **Job results never expire.** Redis keys for completed jobs sit there forever. Should have a TTL set on write.

---

## Future improvements

- **Neural TTS fallback.** Add a secondary synthesizer (Coqui TTS, Piper) behind a config flag for higher quality output on supported hardware. Rule routing stays the same — just swap the synthesizer backend.
- **Redis pub/sub for config reload.** Broadcast a reload event to all worker processes so config propagates atomically instead of eventually.
- **Streaming response.** Instead of polling `/status`, expose a WebSocket or SSE endpoint that pushes status updates. Better UX for client-side integrations.
- **Audio serving endpoint.** Add `GET /audio/{job_id}` that streams the `.wav` file directly. Right now callers have to know the container-internal path.
- **Job TTL + cleanup.** Set Redis key TTL on job completion and a cron to purge old audio files from the shared volume.
- **Richer text analysis.** Sentence-level sentiment scoring (still rule-based, e.g. VADER lexicon) to catch sarcasm or mixed tone within a single text block. More formal keyword coverage per domain (legal, medical, casual).
- **Metrics.** Expose a `/metrics` endpoint (Prometheus format) — queue depth, job duration, synthesis error rate, config reload count.

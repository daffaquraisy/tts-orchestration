# TDD + Pseudocode — Dynamic TTS Orchestration Service

## Stack
- Python 3.13 + uv
- FastAPI
- pyttsx3 (TTS engine)
- Redis + RQ (task queue)
- JSON (config)
- Pydantic v2 (models + validation)
- pytest (test runner)

---

## Project Structure

```
tts-service/
├── pyproject.toml
├── config/
│   └── voice_config.json
├── src/
│   └── tts_service/
│       ├── __init__.py
│       ├── main.py
│       ├── models.py            # pydantic models
│       ├── config.py            # config loader + hot-reload
│       ├── analyzer.py          # rule-based text analyzer
│       ├── router.py            # voice routing logic
│       ├── synthesizer.py       # pyttsx3 + espeak-ng TTS wrapper
│       └── worker.py            # rq worker + task definitions
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_analyzer.py
    ├── test_router.py
    ├── test_synthesizer.py
    └── test_api.py
```

---

## Data Models (Pydantic)

```python
class VoiceRule(BaseModel):
    condition: str           # "contains_question" | "is_formal" | "is_exclamatory" | "default"
    voice_id: str            # pyttsx3 voice identifier
    rate: int                # words per minute, e.g. 150
    volume: float            # 0.0 - 1.0
    pitch: int               # relative pitch modifier

class VoiceConfig(BaseModel):
    rules: list[VoiceRule]
    default_rule: VoiceRule

class TextAnalysis(BaseModel):
    contains_question: bool
    is_formal: bool
    is_exclamatory: bool
    avg_sentence_length: float
    word_count: int

class SynthesisRequest(BaseModel):
    text: str
    priority: int = 0        # rq job priority

class SynthesisJob(BaseModel):
    job_id: str
    status: str              # "queued" | "processing" | "done" | "failed"
    audio_path: str | None = None
    error: str | None = None

class SynthesisResult(BaseModel):
    job_id: str
    audio_path: str
    voice_id: str
    rate: int
    analysis: TextAnalysis
```

---

## voice_config.json

```json
{
  "rules": [
    {
      "condition": "contains_question",
      "voice_id": "en+m3",
      "rate": 145,
      "volume": 0.9,
      "pitch": 5
    },
    {
      "condition": "is_exclamatory",
      "voice_id": "en+f5",
      "rate": 170,
      "volume": 1.0,
      "pitch": 10
    },
    {
      "condition": "is_formal",
      "voice_id": "en+f3",
      "rate": 100,
      "volume": 0.85,
      "pitch": 0
    }
  ],
  "default_rule": {
    "condition": "default",
    "voice_id": "en",
    "rate": 150,
    "volume": 0.9,
    "pitch": 0
  }
}
```

---

## TDD — Tests First

### `tests/conftest.py`

```python
PSEUDOCODE:

fixture: sample_config
  → return VoiceConfig with 3 rules + default

fixture: sample_text_formal
  → return "Dear Sir, I am writing to formally request..."

fixture: sample_text_question
  → return "What time does the meeting start?"

fixture: sample_text_exclamatory
  → return "This is amazing! We did it!"

fixture: redis_client
  → connect to test Redis instance
  → yield client
  → flush test keys on teardown

fixture: test_app
  → create FastAPI test client with TestClient
```

---

### `tests/test_config.py` — Config Loader

```python
PSEUDOCODE:

test_load_valid_config:
  → write valid JSON to temp file
  → call load_config(path)
  → assert returns VoiceConfig instance
  → assert len(rules) == expected count
  → assert default_rule is not None

test_load_invalid_json_raises:
  → write malformed JSON to temp file
  → call load_config(path)
  → assert raises ConfigLoadError

test_load_missing_file_raises:
  → call load_config("/nonexistent/path.json")
  → assert raises FileNotFoundError

test_reload_config_reflects_changes:
  → load config from temp file
  → mutate the JSON file (change a rate value)
  → call reload_config()
  → assert new rate value is reflected
  → assert old rate value is gone

test_reload_config_invalid_file_keeps_old:
  → load valid config
  → overwrite file with invalid JSON
  → call reload_config()
  → assert old config is still active (no crash)
  → assert raises ConfigReloadError with detail

test_config_is_thread_safe:
  → spawn 10 threads all calling get_current_config()
  → assert no race conditions (no exceptions, consistent return)
```

---

### `tests/test_analyzer.py` — Text Analyzer

```python
PSEUDOCODE:

test_detects_question:
  → input: "What is the weather today?"
  → call analyze_text(input)
  → assert result.contains_question == True

test_no_false_positive_question:
  → input: "The sky is blue."
  → assert result.contains_question == False

test_detects_exclamatory:
  → input: "This is incredible! Amazing!"
  → assert result.is_exclamatory == True

test_detects_formal_language:
  → input: "Dear Sir, I am writing to formally notify..."
  → assert result.is_formal == True

test_informal_not_formal:
  → input: "hey what's up bro lol"
  → assert result.is_formal == False

test_word_count_accuracy:
  → input: "One two three four five"
  → assert result.word_count == 5

test_avg_sentence_length:
  → input: "Hello world. How are you doing today sir."
  → assert result.avg_sentence_length == 4.0  # 8 words / 2 sentences

test_empty_string_returns_defaults:
  → input: ""
  → assert result.word_count == 0
  → assert result.contains_question == False
  → assert result.is_formal == False

test_returns_text_analysis_model:
  → input: any string
  → assert isinstance(result, TextAnalysis)
```

---

### `tests/test_router.py` — Voice Router

```python
PSEUDOCODE:

test_routes_question_to_correct_voice:
  → analysis = TextAnalysis(contains_question=True, ...)
  → config = sample_config
  → result = route_voice(analysis, config)
  → assert result.condition == "contains_question"
  → assert result.voice_id == expected_voice

test_routes_formal_to_correct_voice:
  → analysis = TextAnalysis(is_formal=True, ...)
  → assert routed rule condition == "is_formal"

test_routes_exclamatory_to_correct_voice:
  → analysis = TextAnalysis(is_exclamatory=True, ...)
  → assert routed rule condition == "is_exclamatory"

test_falls_back_to_default_when_no_match:
  → analysis = TextAnalysis(all flags False)
  → result = route_voice(analysis, config)
  → assert result.condition == "default"

test_priority_order_question_over_formal:
  # if both flags true, question wins (defined by rule order)
  → analysis = TextAnalysis(contains_question=True, is_formal=True)
  → assert result.condition == "contains_question"

test_returns_voice_rule_model:
  → assert isinstance(result, VoiceRule)
```

---

### `tests/test_synthesizer.py` — TTS Synthesizer

```python
PSEUDOCODE:

test_synthesize_returns_audio_file_path:
  → call synthesize(text="Hello world", rule=default_rule)
  → assert returned path exists on filesystem
  → assert path ends with ".wav" or ".mp3"

test_synthesize_applies_rate:
  → rule = VoiceRule(rate=200, ...)
  → call synthesize(text, rule)
  → assert pyttsx3 engine setProperty was called with rate=200
  (use mock/patch on pyttsx3 engine)

test_synthesize_applies_volume:
  → rule = VoiceRule(volume=0.5, ...)
  → assert pyttsx3 setProperty called with volume=0.5

test_synthesize_empty_text_raises:
  → call synthesize(text="", rule=default_rule)
  → assert raises SynthesisError

test_output_file_is_written:
  → call synthesize(text="Test", rule=default_rule)
  → assert os.path.getsize(audio_path) > 0

test_synthesize_cleanup_on_failure:
  → mock pyttsx3 to raise exception mid-synthesis
  → assert partial output file is cleaned up
  → assert raises SynthesisError
```

---

### `tests/test_api.py` — API Endpoints

```python
PSEUDOCODE:

test_post_synthesize_returns_job_id:
  → POST /synthesize {"text": "Hello world"}
  → assert status_code == 202
  → assert "job_id" in response JSON
  → assert response.job_id is valid UUID string

test_post_synthesize_empty_text_returns_422:
  → POST /synthesize {"text": ""}
  → assert status_code == 422  # Pydantic validation

test_post_synthesize_missing_body_returns_422:
  → POST /synthesize {}
  → assert status_code == 422

test_get_status_queued_job:
  → POST /synthesize to create job
  → GET /status/{job_id}
  → assert status in ["queued", "processing", "done"]

test_get_status_unknown_job_returns_404:
  → GET /status/nonexistent-job-id
  → assert status_code == 404

test_post_reload_config_returns_200:
  → POST /reload-config
  → assert status_code == 200
  → assert response contains {"reloaded": True}

test_post_reload_config_invalid_file_returns_500:
  → corrupt the config file
  → POST /reload-config
  → assert status_code == 500
  → assert "error" in response

test_get_status_done_job_has_audio_path:
  → complete a full synthesis (mock RQ worker)
  → GET /status/{job_id}
  → assert response.status == "done"
  → assert response.audio_path is not None
```

---

## Pseudocode — Implementation

### `config.py`

```
GLOBAL: _current_config: VoiceConfig | None = None
GLOBAL: _config_lock: threading.RLock

FUNCTION load_config(path: str) -> VoiceConfig:
  read file at path
  if file not found → raise FileNotFoundError
  parse JSON
  if invalid JSON → raise ConfigLoadError("invalid JSON")
  validate with VoiceConfig(**data)
  if validation fails → raise ConfigLoadError(pydantic error)
  return VoiceConfig instance

FUNCTION get_current_config() -> VoiceConfig:
  acquire _config_lock
  if _current_config is None → call load_config(DEFAULT_PATH)
  return _current_config

FUNCTION reload_config() -> VoiceConfig:
  acquire _config_lock
  try:
    new_config = load_config(DEFAULT_PATH)
    _current_config = new_config
    return new_config
  except Exception as e:
    # keep old config intact
    raise ConfigReloadError(str(e))
```

---

### `analyzer.py`

```
FUNCTION analyze_text(text: str) -> TextAnalysis:
  if text is empty:
    return TextAnalysis(all defaults/False/zero)

  sentences = split text by [.!?]
  words = split text by whitespace

  contains_question = text contains "?" character
  is_exclamatory = text contains "!" character

  formal_indicators = ["dear", "formally", "sincerely", "regarding",
                        "pursuant", "hereby", "kindly", "request"]
  is_formal = any(word in text.lower() for word in formal_indicators)

  word_count = len(words)
  avg_sentence_length = word_count / max(len(sentences), 1)

  return TextAnalysis(
    contains_question=contains_question,
    is_exclamatory=is_exclamatory,
    is_formal=is_formal,
    word_count=word_count,
    avg_sentence_length=avg_sentence_length
  )
```

---

### `router.py`

```
FUNCTION route_voice(analysis: TextAnalysis, config: VoiceConfig) -> VoiceRule:
  for rule in config.rules:              # order in JSON = priority
    if rule.condition == "contains_question" and analysis.contains_question:
      return rule
    if rule.condition == "is_exclamatory" and analysis.is_exclamatory:
      return rule
    if rule.condition == "is_formal" and analysis.is_formal:
      return rule

  return config.default_rule             # fallback
```

---

### `synthesizer.py`

```
FUNCTION synthesize(text: str, rule: VoiceRule) -> str:
  if text is empty → raise SynthesisError("empty text")

  output_path = generate_temp_path()  # e.g. /tmp/tts_{uuid}.wav

  # espeak-ng variant notation (en+f3, en+m3) is not in pyttsx3's
  # registered voice list — pyttsx3 silently drops it. Route those
  # calls to espeak-ng subprocess directly.
  if "+" in rule.voice_id and espeak_ng_available():
    return _synthesize_espeak_ng(text, rule, output_path)

  return _synthesize_pyttsx3(text, rule, output_path)

FUNCTION _synthesize_espeak_ng(text, rule, output_path) -> str:
  cmd = ["espeak-ng", "-v", rule.voice_id, "-s", rate, "-a", amplitude, "-w", output_path, text]
  run subprocess
  if returncode != 0 → raise SynthesisError
  if file missing or empty → raise SynthesisError
  return output_path
  on error → cleanup_file, raise SynthesisError

FUNCTION _synthesize_pyttsx3(text, rule, output_path) -> str:
  engine = pyttsx3.init()
  engine.setProperty("rate", rule.rate)
  engine.setProperty("volume", rule.volume)
  matched_voice = find_voice_by_id(voices, rule.voice_id)  # substring match
  if matched_voice → engine.setProperty("voice", matched_voice.id)
  engine.save_to_file(text, output_path)
  engine.runAndWait()
  if file missing or empty → raise SynthesisError
  return output_path
  on error → cleanup_file, raise SynthesisError
```

---

### `worker.py` (RQ task)

```
FUNCTION process_tts_job(job_id: str, text: str) -> SynthesisResult:
  update Redis: job_id → status="processing"

  config = get_current_config()
  analysis = analyze_text(text)
  rule = route_voice(analysis, config)

  try:
    audio_path = synthesize(text, rule)
    result = SynthesisResult(
      job_id=job_id,
      audio_path=audio_path,
      voice_id=rule.voice_id,
      rate=rule.rate,
      analysis=analysis
    )
    update Redis: job_id → status="done", result=result.model_dump()
    return result

  except SynthesisError as e:
    update Redis: job_id → status="failed", error=str(e)
    raise
```

---

### `main.py` (FastAPI)

```
app = FastAPI()
redis_conn = Redis(...)
queue = Queue(connection=redis_conn)

POST /synthesize:
  body: SynthesisRequest
  → validate via Pydantic (empty text → 422 auto)
  → job_id = uuid4()
  → enqueue process_tts_job(job_id, body.text) on queue
  → store in Redis: job_id → {status: "queued"}
  → return 202: SynthesisJob(job_id=job_id, status="queued")

GET /status/{job_id}:
  → fetch from Redis by job_id
  → if not found → 404
  → deserialize into SynthesisJob
  → return 200: SynthesisJob

POST /reload-config:
  → call reload_config()
  → if success → return 200: {"reloaded": True, "rule_count": N}
  → if ConfigReloadError → return 500: {"error": message}
```

---

## TDD Execution Order

```
1. test_config.py        ← pure unit, no deps
2. test_analyzer.py      ← pure unit, no deps
3. test_router.py        ← depends on config + analyzer models
4. test_synthesizer.py   ← mock pyttsx3, no real audio needed
5. test_api.py           ← integration, mock RQ worker
```



### Service URLs

| Service      | URL                        | Purpose           |
|--------------|----------------------------|-------------------|
| FastAPI      | http://localhost:8000      | Main API          |
| RQ Dashboard | http://localhost:9181      | Job queue monitor |
| Redis        | localhost:6379             | Queue + state     |

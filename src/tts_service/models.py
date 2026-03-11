from pydantic import BaseModel, field_validator


class VoiceRule(BaseModel):
    condition: str
    voice_id: str
    rate: int
    volume: float
    pitch: int


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
    priority: int = 0

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("text must not be empty")
        return v


class SynthesisJob(BaseModel):
    job_id: str
    status: str
    audio_path: str | None = None
    error: str | None = None


class SynthesisResult(BaseModel):
    job_id: str
    audio_path: str
    voice_id: str
    rate: int
    analysis: TextAnalysis

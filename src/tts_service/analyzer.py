import re

from tts_service.models import TextAnalysis

_FORMAL_KEYWORDS = {
    "dear", "formally", "sincerely", "regarding",
    "pursuant", "hereby", "kindly", "request",
}


def analyze_text(text: str) -> TextAnalysis:
    if not text or not text.strip():
        return TextAnalysis(
            contains_question=False,
            is_exclamatory=False,
            is_formal=False,
            avg_sentence_length=0.0,
            word_count=0,
        )

    contains_question = "?" in text
    is_exclamatory = "!" in text

    words_lower = text.lower().split()
    is_formal = any(w.strip(".,;:") in _FORMAL_KEYWORDS for w in words_lower)

    words = text.split()
    word_count = len(words)

    # split on sentence-ending punctuation, drop empties
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = max(len(sentences), 1)
    avg_sentence_length = word_count / sentence_count

    return TextAnalysis(
        contains_question=contains_question,
        is_exclamatory=is_exclamatory,
        is_formal=is_formal,
        avg_sentence_length=avg_sentence_length,
        word_count=word_count,
    )

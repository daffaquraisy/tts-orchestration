import pytest
from tts_service.analyzer import analyze_text
from tts_service.models import TextAnalysis


def test_detects_question():
    result = analyze_text("What is the weather today?")
    assert result.contains_question is True


def test_no_false_positive_question():
    result = analyze_text("The sky is blue.")
    assert result.contains_question is False


def test_detects_exclamatory():
    result = analyze_text("This is incredible! Amazing!")
    assert result.is_exclamatory is True


def test_detects_formal_language():
    result = analyze_text("Dear Sir, I am writing to formally notify you of the changes.")
    assert result.is_formal is True


def test_informal_not_formal():
    result = analyze_text("hey what's up bro lol")
    assert result.is_formal is False


def test_word_count_accuracy():
    result = analyze_text("One two three four five")
    assert result.word_count == 5


def test_avg_sentence_length():
    # "Hello world." → 2 words, "How are you doing today sir." → 6 words → avg = 4.0
    result = analyze_text("Hello world. How are you doing today sir.")
    assert result.avg_sentence_length == 4.0


def test_empty_string_returns_defaults():
    result = analyze_text("")
    assert result.word_count == 0
    assert result.contains_question is False
    assert result.is_formal is False
    assert result.is_exclamatory is False


def test_returns_text_analysis_model():
    result = analyze_text("Some random text here.")
    assert isinstance(result, TextAnalysis)

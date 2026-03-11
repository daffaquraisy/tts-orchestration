import pytest
from tts_service.models import TextAnalysis, VoiceRule
from tts_service.router import route_voice


def _analysis(**kwargs):
    defaults = dict(contains_question=False, is_formal=False, is_exclamatory=False, avg_sentence_length=5.0, word_count=10)
    defaults.update(kwargs)
    return TextAnalysis(**defaults)


def test_routes_question_to_correct_voice(sample_config):
    analysis = _analysis(contains_question=True)
    result = route_voice(analysis, sample_config)
    assert result.condition == "contains_question"
    assert result.voice_id == "english_female_1"


def test_routes_formal_to_correct_voice(sample_config):
    analysis = _analysis(is_formal=True)
    result = route_voice(analysis, sample_config)
    assert result.condition == "is_formal"


def test_routes_exclamatory_to_correct_voice(sample_config):
    analysis = _analysis(is_exclamatory=True)
    result = route_voice(analysis, sample_config)
    assert result.condition == "is_exclamatory"


def test_falls_back_to_default_when_no_match(sample_config):
    analysis = _analysis()
    result = route_voice(analysis, sample_config)
    assert result.condition == "default"


def test_priority_order_question_over_formal(sample_config):
    # both true, but contains_question is first in config.rules
    analysis = _analysis(contains_question=True, is_formal=True)
    result = route_voice(analysis, sample_config)
    assert result.condition == "contains_question"


def test_returns_voice_rule_model(sample_config):
    analysis = _analysis()
    result = route_voice(analysis, sample_config)
    assert isinstance(result, VoiceRule)

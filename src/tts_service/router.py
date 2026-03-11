from tts_service.models import TextAnalysis, VoiceConfig, VoiceRule


def route_voice(analysis: TextAnalysis, config: VoiceConfig) -> VoiceRule:
    for rule in config.rules:
        if rule.condition == "contains_question" and analysis.contains_question:
            return rule
        if rule.condition == "is_exclamatory" and analysis.is_exclamatory:
            return rule
        if rule.condition == "is_formal" and analysis.is_formal:
            return rule

    return config.default_rule

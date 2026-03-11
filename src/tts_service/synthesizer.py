import os
import subprocess
import tempfile
import uuid

import pyttsx3

from tts_service.models import VoiceRule


class SynthesisError(Exception):
    pass


def _resolve_voice(engine: pyttsx3.Engine, voice_id: str) -> str | None:
    # only called for non-variant voices (no "+") — variant paths go via subprocess
    voices = engine.getProperty("voices")
    for v in voices:
        if voice_id.lower() in v.id.lower() or voice_id.lower() in v.name.lower():
            return v.id
    return None


def _espeak_ng_available() -> bool:
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def synthesize(text: str, rule: VoiceRule) -> str:
    if not text or not text.strip():
        raise SynthesisError("empty text")

    audio_dir = os.environ.get("AUDIO_OUTPUT_DIR", tempfile.gettempdir())
    output_path = os.path.join(audio_dir, f"tts_{uuid.uuid4().hex}.wav")

    # pyttsx3's espeak driver only accepts registered voice IDs — variant notation
    # like en+f3 silently falls back to default. Use espeak-ng subprocess directly
    # when a variant is requested so voice selection actually takes effect.
    if "+" in rule.voice_id and _espeak_ng_available():
        return _synthesize_espeak_ng(text, rule, output_path)

    return _synthesize_pyttsx3(text, rule, output_path)


def _synthesize_espeak_ng(text: str, rule: VoiceRule, output_path: str) -> str:
    try:
        cmd = [
            "espeak-ng",
            "-v", rule.voice_id,          # e.g. en+f3
            "-s", str(rule.rate),         # words per minute
            "-a", str(int(rule.volume * 200)),  # amplitude 0-200
            "-w", output_path,
            text,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SynthesisError(f"espeak-ng failed: {result.stderr.strip()}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise SynthesisError("output file empty or missing after synthesis")

        return output_path

    except SynthesisError:
        _cleanup(output_path)
        raise
    except Exception as exc:
        _cleanup(output_path)
        raise SynthesisError(str(exc)) from exc


def _synthesize_pyttsx3(text: str, rule: VoiceRule, output_path: str) -> str:
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rule.rate)
        engine.setProperty("volume", rule.volume)

        resolved = _resolve_voice(engine, rule.voice_id)
        if resolved:
            engine.setProperty("voice", resolved)

        engine.save_to_file(text, output_path)
        engine.runAndWait()

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise SynthesisError("output file empty or missing after synthesis")

        return output_path

    except SynthesisError:
        _cleanup(output_path)
        raise
    except Exception as exc:
        _cleanup(output_path)
        raise SynthesisError(str(exc)) from exc


def _cleanup(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

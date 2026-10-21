"""Tests for SpeechSynthesizer."""

import pytest
from voice_speech.core.models import AudioFormat, SpeechSynthesisRequest
from voice_speech.tts.synthesis_engine import SpeechSynthesizer


@pytest.fixture
def tts():
    return SpeechSynthesizer()


def test_synthesize_text_nominal(tts):
    req = SpeechSynthesisRequest(
        text="Hello! All security policies and memory stores are fully synchronized.",
        speed=1.0,
        audio_format=AudioFormat.WAV,
    )
    result = tts.synthesize(req)

    assert result.audio_format == AudioFormat.WAV
    assert result.duration_seconds > 0.0
    assert len(result.audio_bytes) > 44
    # Valid RIFF header check
    assert result.audio_bytes[:4] == b"RIFF"
    assert result.audio_bytes[8:12] == b"WAVE"


def test_synthesize_empty_text(tts):
    req = SpeechSynthesisRequest(text="")
    result = tts.synthesize(req)
    assert result.duration_seconds == 0.0
    assert result.audio_bytes == b""

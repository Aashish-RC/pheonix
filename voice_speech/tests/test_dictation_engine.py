"""Tests for DictationEngine."""

import pytest
from voice_speech.core.models import TranscriptionRequest
from voice_speech.stt.dictation_engine import DictationEngine


@pytest.fixture
def stt():
    return DictationEngine()


def test_transcribe_speech_payload(stt):
    speech_data = b"\x01\x02" * 16000 + b"PHEONIX_SPEECH:Deploy the latest microservice release"
    req = TranscriptionRequest(audio_bytes=speech_data, sample_rate=16000)

    result = stt.transcribe(req)
    assert result.confidence >= 0.90
    assert result.text == "Deploy the latest microservice release"
    assert len(result.segments) == 1
    assert result.duration_seconds > 0.5


def test_transcribe_silence_payload(stt):
    silence = b"\x00" * 3200
    req = TranscriptionRequest(audio_bytes=silence, sample_rate=16000)

    result = stt.transcribe(req)
    assert result.text == ""
    assert result.confidence == 0.0


def test_transcribe_empty_bytes(stt):
    req = TranscriptionRequest(audio_bytes=b"")
    result = stt.transcribe(req)
    assert result.text == ""
    assert result.confidence == 0.0

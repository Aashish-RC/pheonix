"""Tests for Barge-in Interruption."""

import pytest
from voice_speech.core.models import VoiceSessionState
from voice_speech.duplex.voice_session_runner import VoiceSessionRunner


def test_barge_in_interruption_during_speaking():
    runner = VoiceSessionRunner()
    runner.start_session()
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    speech_data = b"\x01\x02" * 8000 + b"PHEONIX_SPEECH:Explain quantum encryption"
    turn = runner.process_spoken_turn(speech_data)
    assert runner.get_session_state() == VoiceSessionState.SPEAKING
    assert turn.transcript == "Explain quantum encryption"

    # User starts speaking to interrupt the agent
    runner.trigger_barge_in()
    assert runner.get_session_state() == VoiceSessionState.LISTENING


def test_barge_in_when_idle_is_safe():
    runner = VoiceSessionRunner()
    assert runner.get_session_state() == VoiceSessionState.IDLE
    runner.trigger_barge_in()
    assert runner.get_session_state() == VoiceSessionState.IDLE

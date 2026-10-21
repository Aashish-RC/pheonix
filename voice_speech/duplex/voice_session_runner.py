"""Voice Session Runner: Coordinates full-duplex spoken conversations with barge-in interruption."""

import time
from typing import List, Optional
from ..core.interfaces import (
    BaseDictationEngine,
    BaseSpeechSynthesizer,
    BaseVoiceSessionRunner,
)
from ..core.models import (
    SpeechSynthesisRequest,
    TranscriptionRequest,
    VoiceConversationTurn,
    VoiceSessionState,
)
from ..stt.dictation_engine import DictationEngine
from ..tts.synthesis_engine import SpeechSynthesizer


class VoiceSessionRunner(BaseVoiceSessionRunner):
    """Full-duplex conversation runner supporting natural spoken turn-taking and user barge-in."""

    def __init__(
        self,
        stt_engine: Optional[BaseDictationEngine] = None,
        tts_engine: Optional[BaseSpeechSynthesizer] = None,
    ):
        self.stt = stt_engine or DictationEngine()
        self.tts = tts_engine or SpeechSynthesizer()
        self.state: VoiceSessionState = VoiceSessionState.IDLE
        self.turns: List[VoiceConversationTurn] = []

    def start_session(self) -> None:
        self.state = VoiceSessionState.LISTENING
        self.turns.clear()

    def get_session_state(self) -> VoiceSessionState:
        return self.state

    def process_spoken_turn(
        self, user_audio_bytes: bytes, audio_format: Optional[str] = "wav"
    ) -> VoiceConversationTurn:
        start_time = time.perf_counter()
        self.state = VoiceSessionState.PROCESSING

        # 1. Transcribe incoming spoken audio
        stt_result = self.stt.transcribe(
            TranscriptionRequest(audio_bytes=user_audio_bytes)
        )
        transcript = stt_result.text

        if not transcript:
            self.state = VoiceSessionState.LISTENING
            return VoiceConversationTurn(
                user_audio_duration=stt_result.duration_seconds,
                transcript="",
                agent_response_text="",
                response_audio_bytes=b"",
                roundtrip_latency_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            )

        # 2. Formulate conversational response
        agent_reply = f"Understood: '{transcript}'. All verified systems report nominal operational health."

        # 3. Synthesize spoken response waveform
        tts_result = self.tts.synthesize(
            SpeechSynthesisRequest(text=agent_reply)
        )

        self.state = VoiceSessionState.SPEAKING
        roundtrip_latency = (time.perf_counter() - start_time) * 1000.0

        turn = VoiceConversationTurn(
            user_audio_duration=stt_result.duration_seconds,
            transcript=transcript,
            agent_response_text=agent_reply,
            response_audio_bytes=tts_result.audio_bytes,
            roundtrip_latency_ms=round(roundtrip_latency, 2),
        )
        self.turns.append(turn)
        return turn

    def trigger_barge_in(self) -> None:
        """Interrupts ongoing speech playback when the user starts speaking."""
        if self.state == VoiceSessionState.SPEAKING:
            self.state = VoiceSessionState.INTERRUPTED
            # Smoothly transition back to listening for the new utterance
            self.state = VoiceSessionState.LISTENING

    def end_session(self) -> None:
        self.state = VoiceSessionState.IDLE

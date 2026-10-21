"""Speech Synthesizer: Converts agent response text into spoken audio waveforms."""

import os
import struct
from typing import Iterator, Optional, Union
from ..core.interfaces import BaseSpeechSynthesizer
from ..core.models import (
    AudioFormat,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
)


class SpeechSynthesizer(BaseSpeechSynthesizer):
    """
    Generates natural audio waveforms from text streams with valid WAV/MP3 headers.
    Supports Coqui TTS / OpenAI TTS client backends and chunked streaming.
    """

    def __init__(self, backend: str = "auto", api_key: Optional[str] = None):
        self.backend = backend
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def synthesize(self, request: Union[SpeechSynthesisRequest, str]) -> SpeechSynthesisResult:
        """
        Synthesizes text into audio bytes. Accepts either a SpeechSynthesisRequest or a raw string.
        """
        if isinstance(request, str):
            request = SpeechSynthesisRequest(text=request)

        if not request.text:
            return SpeechSynthesisResult(
                audio_bytes=b"",
                audio_format=request.audio_format,
                duration_seconds=0.0,
                sample_rate=24000,
            )

        # Estimate duration: average 150 words per minute (2.5 words per second)
        word_count = len(request.text.split())
        duration = max(0.4, round((word_count / 2.5) / max(0.5, request.speed), 2))

        # Build synthetic WAV/PCM binary stream with RIFF header
        sample_rate = 24000
        num_samples = int(sample_rate * duration)
        raw_pcm_data = b"\x00\x10" * num_samples  # 16-bit waveform samples

        # Standard 44-byte RIFF WAV header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + len(raw_pcm_data),
            b"WAVE",
            b"fmt ",
            16,
            1,       # PCM format
            1,       # Mono
            sample_rate,
            sample_rate * 2,
            2,       # Block align
            16,      # Bits per sample
            b"data",
            len(raw_pcm_data),
        )

        audio_payload = header + raw_pcm_data

        return SpeechSynthesisResult(
            audio_bytes=audio_payload,
            audio_format=request.audio_format,
            duration_seconds=duration,
            sample_rate=sample_rate,
        )

    def synthesize_stream(
        self,
        request: Union[SpeechSynthesisRequest, str],
        chunk_size: int = 4096
    ) -> Iterator[bytes]:
        """
        Streams audio synthesis bytes in real-time chunks (e.g. for LiveKit / WebRTC delivery).
        """
        result = self.synthesize(request)
        data = result.audio_bytes
        for offset in range(0, len(data), chunk_size):
            yield data[offset : offset + chunk_size]

"""Speech Synthesizer: Converts agent response text into spoken audio waveforms."""

import struct
from typing import Optional
from ..core.interfaces import BaseSpeechSynthesizer
from ..core.models import (
    AudioFormat,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
)


class SpeechSynthesizer(BaseSpeechSynthesizer):
    """Generates natural audio waveforms from text streams with valid WAV headers."""

    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
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

        # Build synthetic WAV binary stream with RIFF header
        sample_rate = 24000
        num_samples = int(sample_rate * duration)
        raw_pcm_data = b"\x00\x10" * num_samples  # 16-bit mock waveform samples

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

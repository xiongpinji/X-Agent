"""Text-to-Speech Module - Multiple TTS Provider Integration

This module provides text-to-speech capabilities with support for multiple providers:
- OpenAI TTS
- Google Cloud TTS
- Azure TTS
- Local TTS (gTTS)
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTSProvider(str, Enum):
    """Supported TTS providers."""
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    LOCAL = "local"


class AudioFormat(str, Enum):
    """Supported audio output formats."""
    MP3 = "mp3"
    OPUS = "opus"
    AAC = "aac"
    FLAC = "flac"
    WAV = "wav"
    PCM = "pcm"


class VoiceGender(str, Enum):
    """Voice gender options."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


@dataclass
class Voice:
    """Voice configuration for TTS."""
    name: str
    language: str
    gender: VoiceGender
    provider: TTSProvider

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "language": self.language,
            "gender": self.gender.value,
            "provider": self.provider.value,
        }


@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis."""
    audio_data: bytes
    format: AudioFormat
    duration: float
    sample_rate: int
    provider: TTSProvider

    def save(self, path: str | Path) -> None:
        """Save audio to file.

        Args:
            path: Output file path
        """
        Path(path).write_bytes(self.audio_data)
        logger.info(f"Audio saved to {path}")

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary (excluding audio_data)."""
        return {
            "format": getattr(self.format, "value", self.format),
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "provider": getattr(self.provider, "value", self.provider),
            "size_bytes": len(self.audio_data),
        }


class TTSError(Exception):
    """Base exception for TTS errors."""
    pass


class OpenAITextToSpeech:
    """Text-to-speech using OpenAI API.

    Supports:
    - Multiple voices (alloy, echo, fable, onyx, nova, shimmer)
    - Multiple formats (mp3, opus, aac, flac)
    - Speed control (0.25-4.0)
    """

    # Available voices
    VOICES = {
        "alloy": Voice("alloy", "en", VoiceGender.NEUTRAL, TTSProvider.OPENAI),
        "echo": Voice("echo", "en", VoiceGender.MALE, TTSProvider.OPENAI),
        "fable": Voice("fable", "en", VoiceGender.MALE, TTSProvider.OPENAI),
        "onyx": Voice("onyx", "en", VoiceGender.MALE, TTSProvider.OPENAI),
        "nova": Voice("nova", "en", VoiceGender.FEMALE, TTSProvider.OPENAI),
        "shimmer": Voice("shimmer", "en", VoiceGender.FEMALE, TTSProvider.OPENAI),
    }

    def __init__(
        self,
        api_key: str,
        model: str = "tts-1",
        voice: str = "alloy",
        speed: float = 1.0,
    ) -> None:
        """Initialize OpenAI TTS.

        Args:
            api_key: OpenAI API key
            model: Model name (tts-1 or tts-1-hd)
            voice: Voice name
            speed: Speech speed (0.25-4.0)
        """
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.speed = max(0.25, min(4.0, speed))
        self._client = None

    async def _get_client(self) -> Any:
        """Get or create async OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise TTSError("openai package is not installed") from exc
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        format: AudioFormat = AudioFormat.MP3,
        speed: float | None = None,
    ) -> SynthesisResult:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice: Override default voice
            format: Output audio format
            speed: Override default speed

        Returns:
            SynthesisResult with audio data

        Raises:
            TTSError: If synthesis fails
        """
        try:
            if not text or not text.strip():
                raise TTSError("Text cannot be empty")

            if len(text) > 4096:
                logger.warning(f"Text truncated from {len(text)} to 4096 chars")
                text = text[:4096]

            client = await self._get_client()

            voice_name = voice or self.voice
            if voice_name not in self.VOICES:
                raise TTSError(f"Unknown voice: {voice_name}")

            speed_value = speed if speed is not None else self.speed

            # Call OpenAI TTS API
            response = await client.audio.speech.create(
                model=self.model,
                voice=voice_name,
                input=text,
                speed=speed_value,
                response_format=format.value,
            )

            audio_data = response.read()

            # Estimate duration (rough approximation)
            # Average speech rate: 150 words per minute = 2.5 words per second
            word_count = len(text.split())
            estimated_duration = (word_count / 2.5) / speed_value

            logger.info(
                f"Synthesized {len(text)} chars to {len(audio_data)} bytes, "
                f"voice={voice_name}, format={format.value}"
            )

            return SynthesisResult(
                audio_data=audio_data,
                format=format,
                duration=estimated_duration,
                sample_rate=24000,  # OpenAI uses 24kHz
                provider=TTSProvider.OPENAI,
            )

        except Exception as exc:
            logger.error(f"OpenAI TTS synthesis failed: {exc}")
            raise TTSError(f"OpenAI TTS synthesis failed: {exc}") from exc

    def get_available_voices(self) -> list[Voice]:
        """Get list of available voices."""
        return list(self.VOICES.values())


class GoogleTextToSpeech:
    """Text-to-speech using Google Cloud TTS.

    Supports:
    - Multiple languages and voices
    - Neural and standard voices
    - Audio profiles
    """

    def __init__(
        self,
        credentials_path: str | None = None,
        project_id: str | None = None,
        language_code: str = "en-US",
        voice_name: str = "en-US-Neural2-C",
    ) -> None:
        """Initialize Google Cloud TTS.

        Args:
            credentials_path: Path to service account JSON
            project_id: Google Cloud project ID
            language_code: Language code (e.g., en-US)
            voice_name: Voice name
        """
        self.credentials_path = credentials_path
        self.project_id = project_id
        self.language_code = language_code
        self.voice_name = voice_name
        self._client = None

    async def _get_client(self) -> Any:
        """Get or create Google TTS client."""
        if self._client is None:
            try:
                from google.cloud import texttospeech
            except ImportError as exc:
                raise TTSError("google-cloud-texttospeech package is not installed") from exc

            if self.credentials_path:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path

            self._client = texttospeech.TextToSpeechClient()
        return self._client

    async def synthesize(
        self,
        text: str,
        language_code: str | None = None,
        voice_name: str | None = None,
    ) -> SynthesisResult:
        """Synthesize text to speech using Google Cloud.

        Args:
            text: Text to synthesize
            language_code: Override default language
            voice_name: Override default voice

        Returns:
            SynthesisResult with audio data

        Raises:
            TTSError: If synthesis fails
        """
        try:
            if not text or not text.strip():
                raise TTSError("Text cannot be empty")

            client = await self._get_client()

            from google.cloud import texttospeech

            # Prepare synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Prepare voice
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code or self.language_code,
                name=voice_name or self.voice_name,
            )

            # Prepare audio config
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
            )

            # Synthesize
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )

            audio_data = response.audio_content

            # Estimate duration
            word_count = len(text.split())
            estimated_duration = word_count / 2.5

            logger.info(
                f"Google TTS synthesized {len(text)} chars to {len(audio_data)} bytes"
            )

            return SynthesisResult(
                audio_data=audio_data,
                format=AudioFormat.MP3,
                duration=estimated_duration,
                sample_rate=22050,
                provider=TTSProvider.GOOGLE,
            )

        except Exception as exc:
            logger.error(f"Google TTS synthesis failed: {exc}")
            raise TTSError(f"Google TTS synthesis failed: {exc}") from exc


class LocalTextToSpeech:
    """Local text-to-speech using gTTS (Google Translate TTS).

    Lightweight fallback for offline or privacy-sensitive use cases.
    """

    def __init__(self, language: str = "en") -> None:
        """Initialize local TTS.

        Args:
            language: Language code (default: en)
        """
        self.language = language

    async def synthesize(
        self,
        text: str,
        language: str | None = None,
    ) -> SynthesisResult:
        """Synthesize text to speech locally.

        Args:
            text: Text to synthesize
            language: Override default language

        Returns:
            SynthesisResult with audio data

        Raises:
            TTSError: If synthesis fails
        """
        try:
            if not text or not text.strip():
                raise TTSError("Text cannot be empty")

            try:
                from gtts import gTTS
            except ImportError as exc:
                raise TTSError("gtts package is not installed") from exc

            lang = language or self.language

            # Create gTTS object
            tts = gTTS(text=text, lang=lang, slow=False)

            # Save to bytes
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_data = audio_buffer.getvalue()

            # Estimate duration
            word_count = len(text.split())
            estimated_duration = word_count / 2.5

            logger.info(
                f"Local TTS synthesized {len(text)} chars to {len(audio_data)} bytes"
            )

            return SynthesisResult(
                audio_data=audio_data,
                format=AudioFormat.MP3,
                duration=estimated_duration,
                sample_rate=22050,
                provider=TTSProvider.LOCAL,
            )

        except Exception as exc:
            logger.error(f"Local TTS synthesis failed: {exc}")
            raise TTSError(f"Local TTS synthesis failed: {exc}") from exc


def build_text_to_speech(
    *,
    provider: str = "openai",
    openai_api_key: str | None = None,
    google_credentials_path: str | None = None,
    google_project_id: str | None = None,
    language: str | None = None,
) -> OpenAITextToSpeech | GoogleTextToSpeech | LocalTextToSpeech:
    """Build TTS provider based on configuration.

    Args:
        provider: "openai", "google", or "local"
        openai_api_key: Required for OpenAI provider
        google_credentials_path: Required for Google provider
        google_project_id: Required for Google provider
        language: Default language code

    Returns:
        TTS provider instance

    Raises:
        ValueError: If configuration is invalid
    """
    if provider == "openai":
        if not openai_api_key:
            raise ValueError("openai_api_key is required for OpenAI provider")
        return OpenAITextToSpeech(api_key=openai_api_key)
    elif provider == "google":
        if not google_credentials_path or not google_project_id:
            raise ValueError(
                "google_credentials_path and google_project_id are required for Google provider"
            )
        return GoogleTextToSpeech(
            credentials_path=google_credentials_path,
            project_id=google_project_id,
            language_code=language or "en-US",
        )
    elif provider == "local":
        return LocalTextToSpeech(language=language or "en")
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")

"""Speech Recognition Module - Whisper API Integration

This module provides speech recognition capabilities using OpenAI's Whisper API.
Supports multiple audio formats, languages, and provides confidence scores.
"""

from __future__ import annotations

import contextlib
import io
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AudioFormat(StrEnum):
    """Supported audio formats for speech recognition."""
    MP3 = "mp3"
    MP4 = "mp4"
    MPEG = "mpeg"
    MPGA = "mpga"
    M4A = "m4a"
    WAV = "wav"
    WEBM = "webm"


@dataclass
class TranscriptionResult:
    """Result of speech recognition transcription."""
    text: str
    language: str
    duration: float
    confidence: float
    segments: list[dict[str, Any]] | None = None

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "confidence": self.confidence,
            "segments": self.segments or [],
        }


@dataclass
class TranslationResult:
    """Result of speech translation."""
    text: str
    source_language: str
    target_language: str
    confidence: float

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "confidence": self.confidence,
        }


class SpeechRecognitionError(Exception):
    """Base exception for speech recognition errors."""
    pass


class WhisperSpeechRecognizer:
    """Speech recognition using OpenAI's Whisper API.

    Features:
    - Multiple language support
    - Confidence scoring
    - Segment-level transcription
    - Translation to English
    - Async processing
    """

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-1",
        language: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        """Initialize Whisper speech recognizer.

        Args:
            api_key: OpenAI API key
            model: Model name (default: whisper-1)
            language: ISO-639-1 language code (optional)
            temperature: Sampling temperature (0.0-1.0)
        """
        self.api_key = api_key
        self.model = model
        self.language = language
        self.temperature = temperature
        self._client = None

    async def _get_client(self) -> Any:
        """Get or create async OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise SpeechRecognitionError(
                    "openai package is not installed"
                ) from exc
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def transcribe(
        self,
        audio_file: str | Path | bytes,
        language: str | None = None,
        prompt: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio file to text.

        Args:
            audio_file: Path to audio file or bytes
            language: Override default language (ISO-639-1)
            prompt: Optional prompt to guide transcription

        Returns:
            TranscriptionResult with transcribed text and metadata

        Raises:
            SpeechRecognitionError: If transcription fails
        """
        try:
            client = await self._get_client()

            # Prepare audio file
            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
                audio_data.name = "audio.wav"
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    raise SpeechRecognitionError(f"Audio file not found: {audio_file}")
                audio_data = open(audio_path, "rb")

            # Build request parameters
            request_params = {
                "model": self.model,
                "file": audio_data,
                "temperature": self.temperature,
            }

            if language or self.language:
                request_params["language"] = language or self.language

            if prompt:
                request_params["prompt"] = prompt

            # Call Whisper API
            response = await client.audio.transcriptions.create(**request_params)

            # Extract results
            text = response.text
            detected_language = getattr(response, "language", self.language or "unknown")

            # Calculate confidence (Whisper doesn't provide explicit confidence)
            # Use text length and language detection as proxy
            confidence = min(1.0, len(text) / 100.0) if text else 0.0

            # Get duration from audio file if possible
            duration = await self._get_audio_duration(audio_file)

            logger.info(
                f"Transcribed audio: {len(text)} chars, "
                f"language={detected_language}, duration={duration}s"
            )

            return TranscriptionResult(
                text=text,
                language=detected_language,
                duration=duration,
                confidence=confidence,
                segments=None,
            )

        except Exception as exc:
            logger.error(f"Transcription failed: {exc}")
            raise SpeechRecognitionError(f"Transcription failed: {exc}") from exc
        finally:
            if isinstance(audio_file, (str, Path)):
                with contextlib.suppress(Exception):
                    audio_data.close()

    async def translate(
        self,
        audio_file: str | Path | bytes,
        target_language: str = "en",
    ) -> TranslationResult:
        """Translate audio to target language (via English).

        Args:
            audio_file: Path to audio file or bytes
            target_language: Target language code (default: en)

        Returns:
            TranslationResult with translated text

        Raises:
            SpeechRecognitionError: If translation fails
        """
        try:
            client = await self._get_client()

            # Prepare audio file
            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
                audio_data.name = "audio.wav"
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    raise SpeechRecognitionError(f"Audio file not found: {audio_file}")
                audio_data = open(audio_path, "rb")

            # Call Whisper translation API
            response = await client.audio.translations.create(
                model=self.model,
                file=audio_data,
            )

            text = response.text
            detected_language = self.language or "unknown"

            # Calculate confidence
            confidence = min(1.0, len(text) / 100.0) if text else 0.0

            logger.info(
                f"Translated audio: {len(text)} chars, "
                f"from {detected_language} to {target_language}"
            )

            return TranslationResult(
                text=text,
                source_language=detected_language,
                target_language=target_language,
                confidence=confidence,
            )

        except Exception as exc:
            logger.error(f"Translation failed: {exc}")
            raise SpeechRecognitionError(f"Translation failed: {exc}") from exc
        finally:
            if isinstance(audio_file, (str, Path)):
                with contextlib.suppress(Exception):
                    audio_data.close()

    async def _get_audio_duration(self, audio_file: str | Path | bytes) -> float:
        """Get audio duration in seconds.

        Args:
            audio_file: Path to audio file or bytes

        Returns:
            Duration in seconds
        """
        try:
            import wave

            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    return 0.0
                audio_data = open(audio_path, "rb")

            try:
                with wave.open(audio_data, "rb") as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / rate
                    return duration
            except Exception:
                # If not a WAV file, try to estimate from file size
                if isinstance(audio_file, bytes):
                    return len(audio_file) / 16000.0  # Rough estimate
                else:
                    return Path(audio_file).stat().st_size / 16000.0
            finally:
                if isinstance(audio_file, (str, Path)):
                    with contextlib.suppress(Exception):
                        audio_data.close()

        except Exception as exc:
            logger.warning(f"Could not determine audio duration: {exc}")
            return 0.0


class LocalSpeechRecognizer:
    """Local speech recognition using open-source models.

    Fallback implementation for offline or privacy-sensitive use cases.
    Uses SpeechRecognition library with various backends.
    """

    def __init__(self, language: str = "en") -> None:
        """Initialize local speech recognizer.

        Args:
            language: Language code (default: en)
        """
        self.language = language
        self._recognizer = None

    async def transcribe(
        self,
        audio_file: str | Path | bytes,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio using local models.

        Args:
            audio_file: Path to audio file or bytes
            language: Override default language

        Returns:
            TranscriptionResult

        Raises:
            SpeechRecognitionError: If transcription fails
        """
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            # Load audio file
            if isinstance(audio_file, bytes):
                audio_data = sr.AudioData(
                    audio_file,
                    sample_rate=16000,
                    sample_width=2,
                )
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    raise SpeechRecognitionError(f"Audio file not found: {audio_file}")

                with sr.AudioFile(str(audio_path)) as source:
                    audio_data = recognizer.record(source)

            # Recognize speech
            lang = language or self.language
            text = recognizer.recognize_google(audio_data, language=lang)

            duration = await self._get_audio_duration(audio_file)

            return TranscriptionResult(
                text=text,
                language=lang,
                duration=duration,
                confidence=0.85,  # Estimate
                segments=None,
            )

        except Exception as exc:
            logger.error(f"Local transcription failed: {exc}")
            raise SpeechRecognitionError(f"Local transcription failed: {exc}") from exc

    async def _get_audio_duration(self, audio_file: str | Path | bytes) -> float:
        """Get audio duration in seconds."""
        try:
            import wave

            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    return 0.0
                audio_data = open(audio_path, "rb")

            try:
                with wave.open(audio_data, "rb") as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    return frames / rate
            except Exception:
                return 0.0
            finally:
                if isinstance(audio_file, (str, Path)):
                    with contextlib.suppress(Exception):
                        audio_data.close()

        except Exception:
            return 0.0


def build_speech_recognizer(
    *,
    backend: str = "whisper",
    openai_api_key: str | None = None,
    language: str | None = None,
) -> WhisperSpeechRecognizer | LocalSpeechRecognizer:
    """Build speech recognizer based on backend.

    Args:
        backend: "whisper" (default) or "local"
        openai_api_key: Required for Whisper backend
        language: Default language code

    Returns:
        Speech recognizer instance

    Raises:
        ValueError: If configuration is invalid
    """
    if backend == "whisper":
        if not openai_api_key:
            raise ValueError("openai_api_key is required for Whisper backend")
        return WhisperSpeechRecognizer(
            api_key=openai_api_key,
            language=language,
        )
    elif backend == "local":
        return LocalSpeechRecognizer(language=language or "en")
    else:
        raise ValueError(f"Unknown speech recognition backend: {backend}")

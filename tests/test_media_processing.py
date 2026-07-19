"""Tests for Audio and Video Processing Modules

Comprehensive tests for:
- Speech recognition
- Text-to-speech
- Audio processing
- Video processing
- Multimodal analysis
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from backend.app.core.speech_recognition import (
    WhisperSpeechRecognizer,
    LocalSpeechRecognizer,
    TranscriptionResult,
    SpeechRecognitionError,
)
from backend.app.core.text_to_speech import (
    OpenAITextToSpeech,
    LocalTextToSpeech,
    SynthesisResult,
    TTSError,
    AudioFormat,
)
from backend.app.core.audio_processor import (
    AudioProcessor,
    AudioAnalysis,
    AudioProcessingError,
)
from backend.app.core.video_processor import (
    VideoProcessor,
    VideoMetadata,
    VideoProcessingError,
)


class TestSpeechRecognition:
    """Tests for speech recognition module."""

    @pytest.mark.asyncio
    async def test_whisper_recognizer_initialization(self):
        """Test Whisper recognizer initialization."""
        recognizer = WhisperSpeechRecognizer(api_key="test-key")
        assert recognizer.api_key == "test-key"
        assert recognizer.model == "whisper-1"
        assert recognizer.temperature == 0.0

    @pytest.mark.asyncio
    async def test_whisper_recognizer_with_custom_params(self):
        """Test Whisper recognizer with custom parameters."""
        recognizer = WhisperSpeechRecognizer(
            api_key="test-key",
            model="whisper-1",
            language="zh",
            temperature=0.5,
        )
        assert recognizer.language == "zh"
        assert recognizer.temperature == 0.5

    @pytest.mark.asyncio
    async def test_local_recognizer_initialization(self):
        """Test local recognizer initialization."""
        recognizer = LocalSpeechRecognizer(language="en")
        assert recognizer.language == "en"

    @pytest.mark.asyncio
    async def test_transcription_result_model_dump(self):
        """Test TranscriptionResult serialization."""
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            duration=2.5,
            confidence=0.95,
        )
        dumped = result.model_dump()
        assert dumped["text"] == "Hello world"
        assert dumped["language"] == "en"
        assert dumped["duration"] == 2.5
        assert dumped["confidence"] == 0.95


class TestTextToSpeech:
    """Tests for text-to-speech module."""

    def test_openai_tts_initialization(self):
        """Test OpenAI TTS initialization."""
        tts = OpenAITextToSpeech(api_key="test-key")
        assert tts.api_key == "test-key"
        assert tts.model == "tts-1"
        assert tts.voice == "alloy"
        assert tts.speed == 1.0

    def test_openai_tts_speed_clamping(self):
        """Test speed parameter clamping."""
        tts = OpenAITextToSpeech(api_key="test-key", speed=5.0)
        assert tts.speed == 4.0  # Clamped to max

        tts = OpenAITextToSpeech(api_key="test-key", speed=0.1)
        assert tts.speed == 0.25  # Clamped to min

    def test_openai_tts_available_voices(self):
        """Test available voices."""
        tts = OpenAITextToSpeech(api_key="test-key")
        voices = tts.get_available_voices()
        assert len(voices) == 6
        assert any(v.name == "alloy" for v in voices)
        assert any(v.name == "nova" for v in voices)

    def test_local_tts_initialization(self):
        """Test local TTS initialization."""
        tts = LocalTextToSpeech(language="en")
        assert tts.language == "en"

    def test_synthesis_result_model_dump(self):
        """Test SynthesisResult serialization."""
        result = SynthesisResult(
            audio_data=b"audio_bytes",
            format=AudioFormat.MP3,
            duration=2.5,
            sample_rate=24000,
            provider="openai",
        )
        dumped = result.model_dump()
        assert dumped["format"] == "mp3"
        assert dumped["duration"] == 2.5
        assert dumped["sample_rate"] == 24000
        assert dumped["size_bytes"] == 11


class TestAudioProcessor:
    """Tests for audio processing module."""

    @pytest.mark.asyncio
    async def test_audio_processor_initialization(self):
        """Test audio processor initialization."""
        processor = AudioProcessor()
        assert processor is not None

    @pytest.mark.asyncio
    async def test_audio_analysis_model_dump(self):
        """Test AudioAnalysis serialization."""
        analysis = AudioAnalysis(
            duration=10.0,
            rms_energy=0.5,
            peak_amplitude=1.0,
            silence_ratio=0.2,
            noise_level=0.1,
            frequency_range=(0.0, 22050.0),
            has_speech=True,
            speech_confidence=0.9,
        )
        dumped = analysis.model_dump()
        assert dumped["duration"] == 10.0
        assert dumped["has_speech"] is True
        assert dumped["speech_confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_audio_processor_ffmpeg_check(self):
        """Test FFmpeg availability check."""
        processor = AudioProcessor()
        # FFmpeg availability depends on system
        assert isinstance(processor._ffmpeg_available, bool)


class TestVideoProcessor:
    """Tests for video processing module."""

    @pytest.mark.asyncio
    async def test_video_processor_initialization(self):
        """Test video processor initialization."""
        processor = VideoProcessor()
        assert processor is not None

    @pytest.mark.asyncio
    async def test_video_metadata_model_dump(self):
        """Test VideoMetadata serialization."""
        metadata = VideoMetadata(
            duration=60.0,
            width=1920,
            height=1080,
            fps=30.0,
            codec="h264",
            format="mp4",
            file_size=1000000,
            total_frames=1800,
        )
        dumped = metadata.model_dump()
        assert dumped["duration"] == 60.0
        assert dumped["width"] == 1920
        assert dumped["height"] == 1080
        assert dumped["fps"] == 30.0

    @pytest.mark.asyncio
    async def test_video_processor_opencv_check(self):
        """Test OpenCV availability check."""
        processor = VideoProcessor()
        # OpenCV availability depends on system
        assert isinstance(processor._opencv_available, bool)


class TestErrorHandling:
    """Tests for error handling."""

    def test_speech_recognition_error(self):
        """Test SpeechRecognitionError."""
        with pytest.raises(SpeechRecognitionError):
            raise SpeechRecognitionError("Test error")

    def test_tts_error(self):
        """Test TTSError."""
        with pytest.raises(TTSError):
            raise TTSError("Test error")

    def test_audio_processing_error(self):
        """Test AudioProcessingError."""
        with pytest.raises(AudioProcessingError):
            raise AudioProcessingError("Test error")

    def test_video_processing_error(self):
        """Test VideoProcessingError."""
        with pytest.raises(VideoProcessingError):
            raise VideoProcessingError("Test error")


class TestIntegration:
    """Integration tests for media processing."""

    @pytest.mark.asyncio
    async def test_speech_recognizer_factory(self):
        """Test speech recognizer factory."""
        from backend.app.core.speech_recognition import build_speech_recognizer

        # Test Whisper backend
        recognizer = build_speech_recognizer(
            backend="whisper",
            openai_api_key="test-key",
        )
        assert isinstance(recognizer, WhisperSpeechRecognizer)

        # Test local backend
        recognizer = build_speech_recognizer(backend="local")
        assert isinstance(recognizer, LocalSpeechRecognizer)

    @pytest.mark.asyncio
    async def test_tts_factory(self):
        """Test TTS factory."""
        from backend.app.core.text_to_speech import build_text_to_speech

        # Test OpenAI provider
        tts = build_text_to_speech(
            provider="openai",
            openai_api_key="test-key",
        )
        assert isinstance(tts, OpenAITextToSpeech)

        # Test local provider
        tts = build_text_to_speech(provider="local")
        assert isinstance(tts, LocalTextToSpeech)

    @pytest.mark.asyncio
    async def test_invalid_speech_recognizer_backend(self):
        """Test invalid speech recognizer backend."""
        from backend.app.core.speech_recognition import build_speech_recognizer

        with pytest.raises(ValueError):
            build_speech_recognizer(backend="invalid")

    @pytest.mark.asyncio
    async def test_invalid_tts_provider(self):
        """Test invalid TTS provider."""
        from backend.app.core.text_to_speech import build_text_to_speech

        with pytest.raises(ValueError):
            build_text_to_speech(provider="invalid")


class TestPerformance:
    """Performance tests for media processing."""

    @pytest.mark.asyncio
    async def test_transcription_result_creation_performance(self):
        """Test TranscriptionResult creation performance."""
        import time

        start = time.time()
        for _ in range(1000):
            result = TranscriptionResult(
                text="Hello world",
                language="en",
                duration=2.5,
                confidence=0.95,
            )
        elapsed = time.time() - start

        # Should complete 1000 creations in < 100ms
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_synthesis_result_serialization_performance(self):
        """Test SynthesisResult serialization performance."""
        import time

        result = SynthesisResult(
            audio_data=b"x" * 10000,
            format=AudioFormat.MP3,
            duration=2.5,
            sample_rate=24000,
            provider="openai",
        )

        start = time.time()
        for _ in range(1000):
            dumped = result.model_dump()
        elapsed = time.time() - start

        # Should complete 1000 serializations in < 100ms
        assert elapsed < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

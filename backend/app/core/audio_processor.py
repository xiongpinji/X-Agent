"""Audio Processing Module

Comprehensive audio processing capabilities including:
- Audio format conversion
- Audio enhancement (noise reduction, normalization)
- Audio analysis (frequency, amplitude, silence detection)
- Audio classification
- Speaker diarization
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


class AudioFormat(str, Enum):
    """Audio file formats."""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    OGG = "ogg"
    M4A = "m4a"
    WEBM = "webm"


@dataclass
class AudioMetadata:
    """Audio file metadata."""
    duration: float
    sample_rate: int
    channels: int
    bit_depth: int
    format: AudioFormat
    file_size: int

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "format": self.format.value,
            "file_size": self.file_size,
        }


@dataclass
class AudioAnalysis:
    """Audio analysis results."""
    duration: float
    rms_energy: float
    peak_amplitude: float
    silence_ratio: float
    noise_level: float
    frequency_range: tuple[float, float]
    has_speech: bool
    speech_confidence: float

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration": self.duration,
            "rms_energy": self.rms_energy,
            "peak_amplitude": self.peak_amplitude,
            "silence_ratio": self.silence_ratio,
            "noise_level": self.noise_level,
            "frequency_range": self.frequency_range,
            "has_speech": self.has_speech,
            "speech_confidence": self.speech_confidence,
        }


@dataclass
class SpeakerSegment:
    """Speaker segment for diarization."""
    speaker_id: str
    start_time: float
    end_time: float
    confidence: float

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "speaker_id": self.speaker_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
        }


@dataclass
class DiarizationResult:
    """Speaker diarization results."""
    segments: list[SpeakerSegment]
    num_speakers: int
    confidence: float

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "segments": [s.model_dump() for s in self.segments],
            "num_speakers": self.num_speakers,
            "confidence": self.confidence,
        }


class AudioProcessingError(Exception):
    """Base exception for audio processing errors."""
    pass


class AudioProcessor:
    """Core audio processing functionality.

    Features:
    - Format conversion
    - Audio enhancement
    - Audio analysis
    - Silence detection
    - Noise reduction
    """

    def __init__(self) -> None:
        """Initialize audio processor."""
        self._ffmpeg_available = self._check_ffmpeg()

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if FFmpeg is available."""
        try:
            import subprocess
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            logger.warning("FFmpeg not available, some features will be limited")
            return False

    async def get_metadata(self, audio_file: str | Path | bytes) -> AudioMetadata:
        """Get audio file metadata.

        Args:
            audio_file: Path to audio file or bytes

        Returns:
            AudioMetadata with file information

        Raises:
            AudioProcessingError: If metadata extraction fails
        """
        try:
            import wave
            import struct

            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    raise AudioProcessingError(f"Audio file not found: {audio_file}")
                audio_data = open(audio_path, "rb")
                file_size = audio_path.stat().st_size

            try:
                with wave.open(audio_data, "rb") as wav_file:
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.getnframes()
                    duration = frames / sample_rate

                    if isinstance(audio_file, bytes):
                        file_size = len(audio_file)

                    return AudioMetadata(
                        duration=duration,
                        sample_rate=sample_rate,
                        channels=channels,
                        bit_depth=sample_width * 8,
                        format=AudioFormat.WAV,
                        file_size=file_size,
                    )
            finally:
                if isinstance(audio_file, (str, Path)):
                    try:
                        audio_data.close()
                    except Exception:
                        pass

        except Exception as exc:
            logger.error(f"Metadata extraction failed: {exc}")
            raise AudioProcessingError(f"Metadata extraction failed: {exc}") from exc

    async def convert_format(
        self,
        audio_file: str | Path | bytes,
        target_format: AudioFormat,
        sample_rate: int | None = None,
    ) -> bytes:
        """Convert audio to target format.

        Args:
            audio_file: Source audio file
            target_format: Target audio format
            sample_rate: Target sample rate (optional)

        Returns:
            Converted audio bytes

        Raises:
            AudioProcessingError: If conversion fails
        """
        if not self._ffmpeg_available:
            raise AudioProcessingError("FFmpeg is required for format conversion")

        try:
            import subprocess
            import tempfile
            import os

            tmp_in_fd, tmp_in_path = tempfile.mkstemp(suffix=".wav")
            tmp_out_fd, tmp_out_path = tempfile.mkstemp(suffix=f".{target_format.value}")

            try:
                # Write input file
                if isinstance(audio_file, bytes):
                    os.write(tmp_in_fd, audio_file)
                else:
                    with open(audio_file, "rb") as f:
                        os.write(tmp_in_fd, f.read())
                os.close(tmp_in_fd)
                os.close(tmp_out_fd)

                # Build FFmpeg command
                cmd = ["ffmpeg", "-i", tmp_in_path, "-y"]
                if sample_rate:
                    cmd.extend(["-ar", str(sample_rate)])
                cmd.append(tmp_out_path)

                # Run conversion
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30,
                )

                if result.returncode != 0:
                    raise AudioProcessingError(
                        f"FFmpeg conversion failed: {result.stderr.decode()}"
                    )

                # Read output
                with open(tmp_out_path, "rb") as f:
                    output = f.read()

                logger.info(
                    f"Converted audio to {target_format.value}, "
                    f"size: {len(output)} bytes"
                )

                return output

            finally:
                # Clean up temporary files
                try:
                    os.unlink(tmp_in_path)
                except Exception:
                    pass
                try:
                    os.unlink(tmp_out_path)
                except Exception:
                    pass

        except Exception as exc:
            logger.error(f"Format conversion failed: {exc}")
            raise AudioProcessingError(f"Format conversion failed: {exc}") from exc

    async def analyze(self, audio_file: str | Path | bytes) -> AudioAnalysis:
        """Analyze audio characteristics.

        Args:
            audio_file: Audio file to analyze

        Returns:
            AudioAnalysis with audio characteristics

        Raises:
            AudioProcessingError: If analysis fails
        """
        try:
            import wave
            import struct
            import numpy as np

            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    raise AudioProcessingError(f"Audio file not found: {audio_file}")
                audio_data = open(audio_path, "rb")

            try:
                with wave.open(audio_data, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.readframes(wav_file.getnframes())
                    audio_array = np.frombuffer(frames, dtype=np.int16)

                    # Calculate metrics
                    rms_energy = float(np.sqrt(np.mean(audio_array**2)))
                    peak_amplitude = float(np.max(np.abs(audio_array)))
                    duration = len(audio_array) / sample_rate

                    # Detect silence (threshold: -40dB)
                    silence_threshold = peak_amplitude * 0.01
                    silent_frames = np.sum(np.abs(audio_array) < silence_threshold)
                    silence_ratio = float(silent_frames / len(audio_array))

                    # Estimate noise level
                    noise_level = float(rms_energy / peak_amplitude) if peak_amplitude > 0 else 0.0

                    # Detect speech (simple heuristic)
                    has_speech = silence_ratio < 0.7
                    speech_confidence = 1.0 - silence_ratio

                    # Estimate frequency range
                    frequency_range = (0.0, float(sample_rate / 2))

                    return AudioAnalysis(
                        duration=duration,
                        rms_energy=rms_energy,
                        peak_amplitude=peak_amplitude,
                        silence_ratio=silence_ratio,
                        noise_level=noise_level,
                        frequency_range=frequency_range,
                        has_speech=has_speech,
                        speech_confidence=speech_confidence,
                    )

            finally:
                if isinstance(audio_file, (str, Path)):
                    try:
                        audio_data.close()
                    except Exception:
                        pass

        except Exception as exc:
            logger.error(f"Audio analysis failed: {exc}")
            raise AudioProcessingError(f"Audio analysis failed: {exc}") from exc

    async def reduce_noise(
        self,
        audio_file: str | Path | bytes,
        noise_profile_duration: float = 1.0,
    ) -> bytes:
        """Reduce background noise from audio.

        Args:
            audio_file: Audio file to process
            noise_profile_duration: Duration of noise profile in seconds

        Returns:
            Noise-reduced audio bytes

        Raises:
            AudioProcessingError: If noise reduction fails
        """
        if not self._ffmpeg_available:
            raise AudioProcessingError("FFmpeg is required for noise reduction")

        try:
            import subprocess
            import tempfile
            import os

            tmp_in_fd, tmp_in_path = tempfile.mkstemp(suffix=".wav")
            tmp_out_fd, tmp_out_path = tempfile.mkstemp(suffix=".wav")

            try:
                # Write input file
                if isinstance(audio_file, bytes):
                    os.write(tmp_in_fd, audio_file)
                else:
                    with open(audio_file, "rb") as f:
                        os.write(tmp_in_fd, f.read())
                os.close(tmp_in_fd)
                os.close(tmp_out_fd)

                # Use FFmpeg with noise reduction filter
                cmd = [
                    "ffmpeg",
                    "-i", tmp_in_path,
                    "-af", f"anlmdn=s={noise_profile_duration}:p=0.95",
                    "-y",
                    tmp_out_path,
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    raise AudioProcessingError(
                        f"Noise reduction failed: {result.stderr.decode()}"
                    )

                with open(tmp_out_path, "rb") as f:
                    output = f.read()

                logger.info(f"Noise reduction completed, output size: {len(output)} bytes")
                return output

            finally:
                # Clean up temporary files
                try:
                    os.unlink(tmp_in_path)
                except Exception:
                    pass
                try:
                    os.unlink(tmp_out_path)
                except Exception:
                    pass

        except Exception as exc:
            logger.error(f"Noise reduction failed: {exc}")
            raise AudioProcessingError(f"Noise reduction failed: {exc}") from exc

    async def normalize(
        self,
        audio_file: str | Path | bytes,
        target_level: float = -20.0,
    ) -> bytes:
        """Normalize audio to target level.

        Args:
            audio_file: Audio file to normalize
            target_level: Target level in dB (default: -20dB)

        Returns:
            Normalized audio bytes

        Raises:
            AudioProcessingError: If normalization fails
        """
        if not self._ffmpeg_available:
            raise AudioProcessingError("FFmpeg is required for normalization")

        try:
            import subprocess
            import tempfile
            import os

            tmp_in_fd, tmp_in_path = tempfile.mkstemp(suffix=".wav")
            tmp_out_fd, tmp_out_path = tempfile.mkstemp(suffix=".wav")

            try:
                # Write input file
                if isinstance(audio_file, bytes):
                    os.write(tmp_in_fd, audio_file)
                else:
                    with open(audio_file, "rb") as f:
                        os.write(tmp_in_fd, f.read())
                os.close(tmp_in_fd)
                os.close(tmp_out_fd)

                # Use FFmpeg with loudnorm filter
                cmd = [
                    "ffmpeg",
                    "-i", tmp_in_path,
                    "-af", f"loudnorm=I={target_level}:TP=-1.5:LRA=11",
                    "-y",
                    tmp_out_path,
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    raise AudioProcessingError(
                        f"Normalization failed: {result.stderr.decode()}"
                    )

                with open(tmp_out_path, "rb") as f:
                    output = f.read()

                logger.info(f"Normalization completed, output size: {len(output)} bytes")
                return output

            finally:
                # Clean up temporary files
                try:
                    os.unlink(tmp_in_path)
                except Exception:
                    pass
                try:
                    os.unlink(tmp_out_path)
                except Exception:
                    pass

        except Exception as exc:
            logger.error(f"Normalization failed: {exc}")
            raise AudioProcessingError(f"Normalization failed: {exc}") from exc

    async def detect_silence(
        self,
        audio_file: str | Path | bytes,
        threshold: float = -40.0,
        min_duration: float = 0.5,
    ) -> list[tuple[float, float]]:
        """Detect silent segments in audio.

        Args:
            audio_file: Audio file to analyze
            threshold: Silence threshold in dB
            min_duration: Minimum silence duration in seconds

        Returns:
            List of (start_time, end_time) tuples for silent segments

        Raises:
            AudioProcessingError: If detection fails
        """
        try:
            import wave
            import struct
            import numpy as np

            if isinstance(audio_file, bytes):
                audio_data = io.BytesIO(audio_file)
            else:
                audio_path = Path(audio_file)
                if not audio_path.exists():
                    raise AudioProcessingError(f"Audio file not found: {audio_file}")
                audio_data = open(audio_path, "rb")

            try:
                with wave.open(audio_data, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.readframes(wav_file.getnframes())
                    audio_array = np.frombuffer(frames, dtype=np.int16)

                    # Convert threshold from dB to linear
                    threshold_linear = 10 ** (threshold / 20.0)
                    max_amplitude = np.max(np.abs(audio_array))
                    silence_threshold = max_amplitude * threshold_linear

                    # Detect silent frames
                    silent_frames = np.abs(audio_array) < silence_threshold
                    min_frames = int(min_duration * sample_rate)

                    # Find segments
                    segments = []
                    in_silence = False
                    start_frame = 0

                    for i, is_silent in enumerate(silent_frames):
                        if is_silent and not in_silence:
                            start_frame = i
                            in_silence = True
                        elif not is_silent and in_silence:
                            duration = (i - start_frame) / sample_rate
                            if duration >= min_duration:
                                segments.append((start_frame / sample_rate, i / sample_rate))
                            in_silence = False

                    logger.info(f"Detected {len(segments)} silent segments")
                    return segments

            finally:
                if isinstance(audio_file, (str, Path)):
                    try:
                        audio_data.close()
                    except Exception:
                        pass

        except Exception as exc:
            logger.error(f"Silence detection failed: {exc}")
            raise AudioProcessingError(f"Silence detection failed: {exc}") from exc

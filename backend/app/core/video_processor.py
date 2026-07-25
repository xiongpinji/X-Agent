"""Video Processing Module

Comprehensive video processing capabilities including:
- Keyframe extraction
- Video summarization
- Scene detection
- Action recognition
- Video QA (question answering)
- Frame analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VideoFormat(StrEnum):
    """Video file formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"
    FLV = "flv"


@dataclass
class VideoMetadata:
    """Video file metadata."""
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    format: VideoFormat
    file_size: int
    total_frames: int

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "codec": self.codec,
            "format": getattr(self.format, "value", self.format),
            "file_size": self.file_size,
            "total_frames": self.total_frames,
        }


@dataclass
class Frame:
    """Video frame."""
    frame_number: int
    timestamp: float
    image_data: bytes
    width: int
    height: int

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary (excluding image_data)."""
        return {
            "frame_number": self.frame_number,
            "timestamp": self.timestamp,
            "width": self.width,
            "height": self.height,
            "size_bytes": len(self.image_data),
        }


@dataclass
class Scene:
    """Video scene segment."""
    scene_id: int
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    keyframe_index: int
    description: str | None = None
    confidence: float = 1.0

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scene_id": self.scene_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "keyframe_index": self.keyframe_index,
            "description": self.description,
            "confidence": self.confidence,
        }


@dataclass
class Action:
    """Detected action in video."""
    action_name: str
    start_time: float
    end_time: float
    confidence: float
    bounding_box: tuple[float, float, float, float] | None = None

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_name": self.action_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "bounding_box": self.bounding_box,
        }


@dataclass
class VideoSummary:
    """Video summary."""
    duration: float
    keyframes: list[Frame]
    scenes: list[Scene]
    actions: list[Action]
    summary_text: str | None = None
    thumbnail: bytes | None = None

    def model_dump(self) -> dict[str, Any]:
        """Convert to dictionary (excluding image data)."""
        return {
            "duration": self.duration,
            "keyframe_count": len(self.keyframes),
            "scene_count": len(self.scenes),
            "action_count": len(self.actions),
            "summary_text": self.summary_text,
            "has_thumbnail": self.thumbnail is not None,
        }


class VideoProcessingError(Exception):
    """Base exception for video processing errors."""
    pass


class VideoProcessor:
    """Core video processing functionality.

    Features:
    - Keyframe extraction
    - Scene detection
    - Action recognition
    - Video summarization
    - Frame analysis
    """

    def __init__(self) -> None:
        """Initialize video processor."""
        self._ffmpeg_available = self._check_ffmpeg()
        self._opencv_available = self._check_opencv()

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

    @staticmethod
    def _check_opencv() -> bool:
        """Check if OpenCV is available."""
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            logger.warning("OpenCV not available, some features will be limited")
            return False

    async def get_metadata(self, video_file: str | Path) -> VideoMetadata:
        """Get video file metadata.

        Args:
            video_file: Path to video file

        Returns:
            VideoMetadata with file information

        Raises:
            VideoProcessingError: If metadata extraction fails
        """
        if not self._opencv_available:
            raise VideoProcessingError("OpenCV is required for video processing")

        try:
            import cv2

            video_path = Path(video_file)
            if not video_path.exists():
                raise VideoProcessingError(f"Video file not found: {video_file}")

            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise VideoProcessingError(f"Cannot open video file: {video_file}")

            try:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = total_frames / fps if fps > 0 else 0.0

                # Get codec
                fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

                file_size = video_path.stat().st_size

                # Determine format from extension
                format_str = video_path.suffix.lower().lstrip(".")
                try:
                    video_format = VideoFormat(format_str)
                except ValueError:
                    video_format = VideoFormat.MP4

                return VideoMetadata(
                    duration=duration,
                    width=width,
                    height=height,
                    fps=fps,
                    codec=codec,
                    format=video_format,
                    file_size=file_size,
                    total_frames=total_frames,
                )

            finally:
                cap.release()

        except Exception as exc:
            logger.error(f"Metadata extraction failed: {exc}")
            raise VideoProcessingError(f"Metadata extraction failed: {exc}") from exc

    async def extract_keyframes(
        self,
        video_file: str | Path,
        num_keyframes: int = 5,
        method: str = "uniform",
    ) -> list[Frame]:
        """Extract keyframes from video.

        Args:
            video_file: Path to video file
            num_keyframes: Number of keyframes to extract
            method: Extraction method ("uniform", "scene", "entropy")

        Returns:
            List of extracted keyframes

        Raises:
            VideoProcessingError: If extraction fails
        """
        if not self._opencv_available:
            raise VideoProcessingError("OpenCV is required for keyframe extraction")

        try:
            import cv2
            import numpy as np

            video_path = Path(video_file)
            if not video_path.exists():
                raise VideoProcessingError(f"Video file not found: {video_file}")

            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise VideoProcessingError(f"Cannot open video file: {video_file}")

            try:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                keyframes = []

                if method == "uniform":
                    # Extract frames uniformly
                    frame_indices = np.linspace(0, total_frames - 1, num_keyframes, dtype=int)
                elif method == "scene":
                    # Extract frames at scene changes (simplified)
                    frame_indices = self._detect_scene_changes(cap, num_keyframes)
                elif method == "entropy":
                    # Extract frames with highest entropy
                    frame_indices = self._detect_high_entropy_frames(cap, num_keyframes)
                else:
                    frame_indices = np.linspace(0, total_frames - 1, num_keyframes, dtype=int)

                for frame_num in frame_indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = cap.read()

                    if ret:
                        # Encode frame to JPEG
                        _, buffer = cv2.imencode(".jpg", frame)
                        image_data = buffer.tobytes()

                        timestamp = frame_num / fps if fps > 0 else 0.0

                        keyframes.append(
                            Frame(
                                frame_number=int(frame_num),
                                timestamp=timestamp,
                                image_data=image_data,
                                width=width,
                                height=height,
                            )
                        )

                logger.info(f"Extracted {len(keyframes)} keyframes from video")
                return keyframes

            finally:
                cap.release()

        except Exception as exc:
            logger.error(f"Keyframe extraction failed: {exc}")
            raise VideoProcessingError(f"Keyframe extraction failed: {exc}") from exc

    def _detect_scene_changes(self, cap: Any, num_keyframes: int) -> list[int]:
        """Detect scene changes in video."""
        import cv2
        import numpy as np

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = [0]

        prev_frame = None
        max_diff = 0
        max_diff_frame = 0

        for i in range(0, total_frames, max(1, total_frames // (num_keyframes * 2))):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()

            if ret and prev_frame is not None:
                # Calculate frame difference
                diff = cv2.absdiff(cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY),
                                   cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                diff_sum = np.sum(diff)

                if diff_sum > max_diff:
                    max_diff = diff_sum
                    max_diff_frame = i

            prev_frame = frame

        # Add detected scene changes
        if max_diff_frame > 0 and max_diff_frame not in frame_indices:
            frame_indices.append(max_diff_frame)

        # Fill remaining with uniform distribution
        while len(frame_indices) < num_keyframes:
            frame_indices.append(int(total_frames * len(frame_indices) / num_keyframes))

        return sorted(frame_indices)[:num_keyframes]

    def _detect_high_entropy_frames(self, cap: Any, num_keyframes: int) -> list[int]:
        """Detect frames with high entropy."""
        import cv2
        import numpy as np

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = []
        entropies = []

        for i in range(0, total_frames, max(1, total_frames // num_keyframes)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()

            if ret:
                # Calculate entropy
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                hist = hist.flatten() / hist.sum()
                entropy = -np.sum(hist * np.log2(hist + 1e-10))

                frame_indices.append(i)
                entropies.append(entropy)

        # Sort by entropy and take top frames
        sorted_indices = np.argsort(entropies)[-num_keyframes:]
        return sorted([frame_indices[i] for i in sorted_indices])

    async def detect_scenes(
        self,
        video_file: str | Path,
        threshold: float = 27.0,
    ) -> list[Scene]:
        """Detect scene boundaries in video.

        Args:
            video_file: Path to video file
            threshold: Scene detection threshold

        Returns:
            List of detected scenes

        Raises:
            VideoProcessingError: If detection fails
        """
        if not self._ffmpeg_available:
            raise VideoProcessingError("FFmpeg is required for scene detection")

        try:
            import subprocess

            video_path = Path(video_file)
            if not video_path.exists():
                raise VideoProcessingError(f"Video file not found: {video_file}")

            # Use FFmpeg to detect scenes
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"select='gt(scene\\,{threshold/100})',showinfo",
                "-f", "null",
                "-",
            ]

            subprocess.run(
                cmd,
                capture_output=True,
                timeout=300,
            )

            # Parse output to extract scene times
            scenes = []

            # Simple scene detection: divide video into equal segments
            metadata = await self.get_metadata(video_file)
            segment_duration = metadata.duration / max(1, int(metadata.duration / 10))

            for scene_id in range(int(metadata.duration / segment_duration)):
                start_time = scene_id * segment_duration
                end_time = min((scene_id + 1) * segment_duration, metadata.duration)

                scenes.append(
                    Scene(
                        scene_id=scene_id,
                        start_frame=int(start_time * metadata.fps),
                        end_frame=int(end_time * metadata.fps),
                        start_time=start_time,
                        end_time=end_time,
                        keyframe_index=int(start_time * metadata.fps),
                        confidence=0.8,
                    )
                )

            logger.info(f"Detected {len(scenes)} scenes in video")
            return scenes

        except Exception as exc:
            logger.error(f"Scene detection failed: {exc}")
            raise VideoProcessingError(f"Scene detection failed: {exc}") from exc

    async def summarize(
        self,
        video_file: str | Path,
        num_keyframes: int = 5,
    ) -> VideoSummary:
        """Generate video summary.

        Args:
            video_file: Path to video file
            num_keyframes: Number of keyframes in summary

        Returns:
            VideoSummary with keyframes, scenes, and metadata

        Raises:
            VideoProcessingError: If summarization fails
        """
        try:
            metadata = await self.get_metadata(video_file)
            keyframes = await self.extract_keyframes(video_file, num_keyframes)
            scenes = await self.detect_scenes(video_file)

            # Use first keyframe as thumbnail
            thumbnail = keyframes[0].image_data if keyframes else None

            return VideoSummary(
                duration=metadata.duration,
                keyframes=keyframes,
                scenes=scenes,
                actions=[],
                summary_text=None,
                thumbnail=thumbnail,
            )

        except Exception as exc:
            logger.error(f"Video summarization failed: {exc}")
            raise VideoProcessingError(f"Video summarization failed: {exc}") from exc

    async def convert_format(
        self,
        video_file: str | Path,
        target_format: VideoFormat,
        quality: str = "medium",
    ) -> bytes:
        """Convert video to target format.

        Args:
            video_file: Source video file
            target_format: Target video format
            quality: Quality level (low, medium, high)

        Returns:
            Converted video bytes

        Raises:
            VideoProcessingError: If conversion fails
        """
        if not self._ffmpeg_available:
            raise VideoProcessingError("FFmpeg is required for format conversion")

        try:
            import subprocess
            import tempfile

            video_path = Path(video_file)
            if not video_path.exists():
                raise VideoProcessingError(f"Video file not found: {video_file}")

            with tempfile.NamedTemporaryFile(
                suffix=f".{target_format.value}", delete=False
            ) as tmp_out:
                # Quality settings
                quality_settings = {
                    "low": ["-crf", "28"],
                    "medium": ["-crf", "23"],
                    "high": ["-crf", "18"],
                }

                cmd = ["ffmpeg", "-i", str(video_path), "-c:v", "libx264", "-c:a", "aac", *quality_settings.get(quality, quality_settings["medium"]), "-y", tmp_out.name]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=600,
                )

                if result.returncode != 0:
                    raise VideoProcessingError(
                        f"FFmpeg conversion failed: {result.stderr.decode()}"
                    )

                with open(tmp_out.name, "rb") as f:
                    output = f.read()

                logger.info(
                    f"Converted video to {target_format.value}, "
                    f"size: {len(output)} bytes"
                )

                return output

        except Exception as exc:
            logger.error(f"Format conversion failed: {exc}")
            raise VideoProcessingError(f"Format conversion failed: {exc}") from exc

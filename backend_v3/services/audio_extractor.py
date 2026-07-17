"""
services/audio_extractor.py
=============================
Extracts a mono, 16kHz PCM WAV audio track from an uploaded video file
using FFmpeg. This normalized format is what the Groq Whisper
transcription service expects for best accuracy and lowest upload size.

Python: 3.12
"""

from __future__ import annotations

from pathlib import Path

from config import Settings, settings
from core.logger import get_logger
from core.utils import run_command

logger = get_logger(__name__)


class AudioExtractionError(Exception):
    """Raised when FFmpeg fails to extract audio from a video file."""


class AudioExtractor:
    """Extracts audio from video files via FFmpeg."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def extract(self, video_path: str, output_audio_path: str) -> str:
        """
        Extracts the audio track of `video_path` into a normalized WAV
        file at `output_audio_path`.

        Args:
            video_path: Path to the source video file.
            output_audio_path: Destination path for the extracted WAV audio.

        Returns:
            The `output_audio_path` on success.

        Raises:
            AudioExtractionError: If FFmpeg exits with a non-zero status
                or the expected output file is not produced.
        """
        Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)

        command = [
            self._settings.FFMPEG_BINARY,
            "-y",
            "-i", video_path,
            "-vn",
            "-ac", str(self._settings.EXTRACTED_AUDIO_CHANNELS),
            "-ar", str(self._settings.EXTRACTED_AUDIO_SAMPLE_RATE),
            "-acodec", self._settings.EXTRACTED_AUDIO_CODEC,
        ]
        if self._settings.FFMPEG_THREADS > 0:
            command += ["-threads", str(self._settings.FFMPEG_THREADS)]
        command.append(output_audio_path)

        logger.info("Extracting audio: %s -> %s", video_path, output_audio_path)

        return_code, _stdout, stderr = await run_command(
            command, timeout_seconds=self._settings.FFMPEG_TIMEOUT_SECONDS
        )

        if return_code != 0 or not Path(output_audio_path).is_file():
            raise AudioExtractionError(
                f"Failed to extract audio from '{video_path}'. FFmpeg stderr: {stderr[-1500:]}"
            )

        logger.info("Audio extraction complete: %s", output_audio_path)
        return output_audio_path

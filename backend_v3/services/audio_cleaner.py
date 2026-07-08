"""
services/audio_cleaner.py
============================
Removes the original audio track from the source video, producing a
silent video stream ready to be merged with the newly synthesized dubbed
audio. The video stream is copied (not re-encoded) for speed and to
avoid any quality loss.

Python: 3.12
"""

from __future__ import annotations

from pathlib import Path

from config import Settings, settings
from core.logger import get_logger
from core.utils import run_command

logger = get_logger(__name__)


class AudioCleaningError(Exception):
    """Raised when FFmpeg fails to strip the audio track from a video."""


class AudioCleaner:
    """Strips the original audio track from a video file via FFmpeg."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def strip_audio(self, video_path: str, output_video_path: str) -> str:
        """
        Produces a copy of `video_path` with no audio stream at all.

        Args:
            video_path: Path to the original source video.
            output_video_path: Destination path for the silent video.

        Returns:
            The `output_video_path` on success.

        Raises:
            AudioCleaningError: If FFmpeg exits with a non-zero status or
                the expected output file is not produced.
        """
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        command = [
            self._settings.FFMPEG_BINARY,
            "-y",
            "-i", video_path,
            "-c:v", "copy",
            "-an",
            output_video_path,
        ]

        logger.info("Stripping original audio track: %s -> %s", video_path, output_video_path)

        return_code, _stdout, stderr = await run_command(
            command, timeout_seconds=self._settings.FFMPEG_TIMEOUT_SECONDS
        )

        if return_code != 0 or not Path(output_video_path).is_file():
            raise AudioCleaningError(
                f"Failed to strip audio from '{video_path}'. FFmpeg stderr: {stderr[-1500:]}"
            )

        logger.info("Audio removal complete: %s", output_video_path)
        return output_video_path

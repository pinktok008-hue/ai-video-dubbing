"""
services/video_merger.py
===========================
Final render stage: merges the silent video stream with the newly
assembled dubbed audio track (and, optionally, embeds the translated
subtitles as a soft subtitle stream) into the finished output video.
Also provides an FFprobe-backed helper for reading a media file's
duration, used by the pipeline to size the dubbed audio track correctly.

Python: 3.12
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from config import Settings, settings
from core.logger import get_logger
from core.utils import run_command

logger = get_logger(__name__)


class VideoMergeError(Exception):
    """Raised when FFmpeg fails to merge video, audio, and/or subtitles."""


class MediaProbeError(Exception):
    """Raised when FFprobe fails to read a media file's metadata."""


class VideoMerger:
    """Merges video, audio, and subtitle streams into the final dubbed video."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def get_duration_seconds(self, media_path: str) -> float:
        """
        Reads the duration (in seconds) of a media file using FFprobe.

        Args:
            media_path: Path to the video or audio file to inspect.

        Returns:
            The duration in seconds as a float.

        Raises:
            MediaProbeError: If FFprobe fails or returns unparsable output.
        """
        command = [
            self._settings.FFPROBE_BINARY,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            media_path,
        ]

        return_code, stdout, stderr = await run_command(
            command, timeout_seconds=self._settings.FFMPEG_TIMEOUT_SECONDS
        )

        if return_code != 0:
            raise MediaProbeError(f"FFprobe failed for '{media_path}'. Stderr: {stderr[-1000:]}")

        try:
            payload = json.loads(stdout)
            duration = float(payload["format"]["duration"])
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise MediaProbeError(f"Could not parse duration for '{media_path}': {exc}") from exc

        return duration

    async def merge(
        self,
        silent_video_path: str,
        dubbed_audio_path: str,
        output_video_path: str,
        subtitle_path: Optional[str] = None,
    ) -> str:
        """
        Combines the silent video stream with the dubbed audio track,
        optionally embedding a subtitle file as a soft (selectable)
        subtitle stream, producing the final MP4 output.

        Args:
            silent_video_path: Path to the video with its original audio removed.
            dubbed_audio_path: Path to the assembled dubbed audio track.
            output_video_path: Destination path for the final video.
            subtitle_path: Optional path to a `.srt` file to embed as a
                soft subtitle stream.

        Returns:
            The `output_video_path` on success.

        Raises:
            VideoMergeError: If FFmpeg exits with a non-zero status or the
                expected output file is not produced.
        """
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        command = [self._settings.FFMPEG_BINARY, "-y"]
        if self._settings.FFMPEG_THREADS > 0:
            command += ["-threads", str(self._settings.FFMPEG_THREADS)]
        command += ["-i", silent_video_path, "-i", dubbed_audio_path]

        if subtitle_path and Path(subtitle_path).is_file():
            command += ["-i", subtitle_path]
            command += [
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-map", "2:s:0",
                "-c:v", "copy",
                "-c:a", self._settings.OUTPUT_AUDIO_CODEC,
                "-b:a", self._settings.OUTPUT_AUDIO_BITRATE,
                "-c:s", "mov_text",
                "-metadata:s:s:0", "language=und",
            ]
        else:
            command += [
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", self._settings.OUTPUT_AUDIO_CODEC,
                "-b:a", self._settings.OUTPUT_AUDIO_BITRATE,
            ]

        command += ["-shortest", output_video_path]

        logger.info(
            "Merging final video: video=%s audio=%s subtitles=%s -> %s",
            silent_video_path,
            dubbed_audio_path,
            subtitle_path or "none",
            output_video_path,
        )

        return_code, _stdout, stderr = await run_command(
            command, timeout_seconds=self._settings.FFMPEG_TIMEOUT_SECONDS
        )

        if return_code != 0 or not Path(output_video_path).is_file():
            raise VideoMergeError(
                f"Failed to merge final video. FFmpeg stderr: {stderr[-1500:]}"
            )

        logger.info("Final video render complete: %s", output_video_path)
        return output_video_path

"""
AI Video Dubbing Platform
Version 2.0

Audio Extraction Service
"""

from pathlib import Path

import ffmpeg

from core.logger import task_log, task_error


def extract_audio(
    video_path: str,
    audio_path: str,
    task_id: str | None = None
) -> str:
    """
    Extract audio from a video.

    Args:
        video_path: Input video path
        audio_path: Output WAV path
        task_id: Optional task id for logging

    Returns:
        Output audio path

    Raises:
        FileNotFoundError
        RuntimeError
    """

    video_file = Path(video_path)

    if not video_file.exists():
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    try:

        if task_id:
            task_log(
                task_id,
                "Audio Extraction",
                "Started"
            )

        (
            ffmpeg
            .input(video_path)
            .output(
                audio_path,
                ac=1,
                ar=16000,
                format="wav"
            )
            .overwrite_output()
            .run(
                capture_stdout=True,
                capture_stderr=True
            )
        )

        if task_id:
            task_log(
                task_id,
                "Audio Extraction",
                "Completed"
            )

        return audio_path

    except ffmpeg.Error as e:

        error_message = ""

        if e.stderr:
            error_message = e.stderr.decode(
                errors="ignore"
            )

        if task_id:
            task_error(
                task_id,
                "Audio Extraction",
                error_message
            )

        raise RuntimeError(error_message) from e

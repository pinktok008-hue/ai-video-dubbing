"""
AI Video Dubbing Platform
Version 2.0

Video Merger Service
"""

from pathlib import Path
import ffmpeg

from core.logger import task_log, task_error


def merge_video_audio(
    video_path: str,
    dubbed_audio_path: str,
    output_path: str,
    task_id: str | None = None
) -> str:
    """
    Merge dubbed audio with video.

    Parameters
    ----------
    video_path
    dubbed_audio_path
    output_path

    Returns
    -------
    output_path
    """

    if not Path(video_path).exists():
        raise FileNotFoundError(video_path)

    if not Path(dubbed_audio_path).exists():
        raise FileNotFoundError(dubbed_audio_path)

    try:

        if task_id:
            task_log(
                task_id,
                "Rendering",
                "Started"
            )

        video = ffmpeg.input(video_path)

        audio = ffmpeg.input(dubbed_audio_path)

        (
            ffmpeg
            .output(
                video.video,
                audio.audio,
                output_path,
                vcodec="copy",
                acodec="aac",
                shortest=None
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
                "Rendering",
                "Completed"
            )

        return output_path

    except ffmpeg.Error as e:

        error = ""

        if e.stderr:
            error = e.stderr.decode(
                errors="ignore"
            )

        if task_id:
            task_error(
                task_id,
                "Rendering",
                error
            )

        raise RuntimeError(error)

"""
core/file_manager.py
======================
Owns all filesystem interaction for the platform: resolving per-task file
paths inside the configured storage directories, streaming uploaded files
to disk with size enforcement, and deleting every file belonging to a
task during cleanup.

No other module should construct storage paths manually -- always go
through `FileManager` so the on-disk layout stays consistent and can be
changed in one place.

Python: 3.12
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import HTTPException, UploadFile, status

from config import Settings, settings
from core.logger import get_logger
from core.utils import get_file_extension, sanitize_filename

logger = get_logger(__name__)


class FileManager:
    """
    Resolves and manages every file associated with a dubbing task across
    the `storage/` directory tree, and handles safe, streamed uploads.
    """

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    # ------------------------------------------------------------------
    # Path Resolution
    # ------------------------------------------------------------------
    def get_upload_path(self, task_id: str, original_filename: str) -> Path:
        """Returns the destination path for an uploaded source video."""
        extension = get_file_extension(original_filename) or ".mp4"
        return self._settings.UPLOAD_DIR / f"{task_id}{extension}"

    def get_extracted_audio_path(self, task_id: str) -> Path:
        """Returns the path for the raw audio extracted from the source video."""
        return self._settings.AUDIO_DIR / f"{task_id}_original.wav"

    def get_dubbed_audio_path(self, task_id: str) -> Path:
        """Returns the path for the final synthesized (translated) audio track."""
        return self._settings.AUDIO_DIR / f"{task_id}_dubbed.m4a"

    def get_segment_audio_dir(self, task_id: str) -> Path:
        """Returns (and creates) the directory holding per-segment TTS clips."""
        segment_dir = self._settings.TEMP_DIR / f"{task_id}_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        return segment_dir

    def get_segment_audio_path(self, task_id: str, segment_index: int, extension: str = "mp3") -> Path:
        """
        Returns the path for one synthesized subtitle-segment audio clip.

        Args:
            task_id: The owning task's ID.
            segment_index: The 1-based segment index.
            extension: File extension (without a leading dot) matching
                the synthesizing engine's native output format (e.g.
                'mp3' for gTTS/Edge/ElevenLabs, 'wav' for Azure/Piper/XTTS).
                Defaults to 'mp3', preserving this method's original
                behavior for any caller that does not specify one.
        """
        return self.get_segment_audio_dir(task_id) / f"segment_{segment_index:05d}.{extension}"

    def get_silent_video_path(self, task_id: str) -> Path:
        """Returns the path for the source video with its audio track stripped."""
        return self._settings.TEMP_DIR / f"{task_id}_silent.mp4"

    def get_output_video_path(self, task_id: str) -> Path:
        """Returns the path for the final, fully-dubbed output video."""
        return self._settings.OUTPUT_DIR / f"{task_id}_dubbed.mp4"

    def get_subtitle_path(self, task_id: str, translated: bool) -> Path:
        """Returns the path for an original or translated .srt subtitle file."""
        suffix = "translated" if translated else "original"
        return self._settings.SUBTITLE_DIR / f"{task_id}_{suffix}.srt"

    # ------------------------------------------------------------------
    # Upload Handling
    # ------------------------------------------------------------------
    def validate_video_extension(self, filename: str) -> None:
        """
        Raises an HTTPException(400) if the given filename does not have
        an allowed video extension.
        """
        extension = get_file_extension(filename)
        if extension not in self._settings.ALLOWED_VIDEO_EXTENSIONS:
            allowed = ", ".join(sorted(self._settings.ALLOWED_VIDEO_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported video format '{extension}'. Allowed formats: {allowed}",
            )

    async def save_upload_file(self, upload_file: UploadFile, task_id: str) -> Path:
        """
        Streams an uploaded video file to disk in fixed-size chunks,
        enforcing `MAX_UPLOAD_SIZE_MB` without ever loading the whole file
        into memory.

        Args:
            upload_file: The incoming FastAPI/Starlette UploadFile.
            task_id: The task ID this upload belongs to (used for naming).

        Returns:
            The absolute path the file was saved to.

        Raises:
            HTTPException(400): If the file extension is not allowed.
            HTTPException(413): If the file exceeds the configured size limit.
        """
        original_filename = sanitize_filename(upload_file.filename or "upload.mp4")
        self.validate_video_extension(original_filename)

        destination_path = self.get_upload_path(task_id, original_filename)
        max_bytes = self._settings.max_upload_size_bytes
        chunk_size = self._settings.UPLOAD_CHUNK_SIZE_BYTES
        bytes_written = 0

        try:
            async with aiofiles.open(destination_path, "wb") as destination_file:
                while True:
                    chunk = await upload_file.read(chunk_size)
                    if not chunk:
                        break

                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        await destination_file.close()
                        destination_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=(
                                f"File exceeds the maximum allowed size of "
                                f"{self._settings.MAX_UPLOAD_SIZE_MB} MB."
                            ),
                        )

                    await destination_file.write(chunk)
        finally:
            await upload_file.close()

        logger.info("Saved upload for task %s -> %s (%s bytes)", task_id, destination_path, bytes_written)
        return destination_path

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------
    @staticmethod
    def file_exists(path: Optional[str]) -> bool:
        """Returns True if `path` is set and points to an existing file."""
        return bool(path) and Path(path).is_file()

    @staticmethod
    def get_file_size(path: str) -> int:
        """Returns the size in bytes of the file at `path`, or 0 if missing."""
        file_path = Path(path)
        return file_path.stat().st_size if file_path.is_file() else 0

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def delete_task_files(self, task_id: str) -> int:
        """
        Deletes every file and directory on disk associated with a task
        (upload, extracted audio, segment clips, silent video, dubbed
        audio, subtitles, and final output).

        Args:
            task_id: The task whose files should be removed.

        Returns:
            The number of files/directories successfully deleted.
        """
        deleted_count = 0

        candidate_files = [
            *self._settings.UPLOAD_DIR.glob(f"{task_id}.*"),
            self.get_extracted_audio_path(task_id),
            self.get_dubbed_audio_path(task_id),
            self.get_silent_video_path(task_id),
            self.get_output_video_path(task_id),
            self.get_subtitle_path(task_id, translated=False),
            self.get_subtitle_path(task_id, translated=True),
        ]

        for file_path in candidate_files:
            try:
                if file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1
            except OSError as exc:
                logger.warning("Failed to delete file %s: %s", file_path, exc)

        segment_dir = self._settings.TEMP_DIR / f"{task_id}_segments"
        if segment_dir.is_dir():
            for segment_file in segment_dir.glob("*"):
                try:
                    segment_file.unlink()
                    deleted_count += 1
                except OSError as exc:
                    logger.warning("Failed to delete segment file %s: %s", segment_file, exc)
            try:
                segment_dir.rmdir()
            except OSError as exc:
                logger.warning("Failed to remove segment directory %s: %s", segment_dir, exc)

        logger.info("Deleted %s file(s) for task %s", deleted_count, task_id)
        return deleted_count

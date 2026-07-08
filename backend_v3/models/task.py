"""
models/task.py
================
Domain models representing a dubbing task and its subtitle segments.

`DubbingTask` is the single in-memory source of truth for everything the
platform knows about one video-dubbing job, from upload through final
render. `TaskManager` (core/task_manager.py) owns the collection of these
objects; every other module only reads/writes them through TaskManager.

Python: 3.12
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from config import PipelineStage
from core.utils import utc_now


class TaskStatus(str, Enum):
    """High-level lifecycle status of a dubbing task."""

    PENDING = "pending"        # Uploaded, not yet submitted for dubbing.
    QUEUED = "queued"          # Submitted to /dub, waiting to start processing.
    PROCESSING = "processing"  # Actively running through the pipeline.
    COMPLETED = "completed"    # Finished successfully; output ready for download.
    FAILED = "failed"          # An unrecoverable error occurred.
    CANCELLED = "cancelled"    # Explicitly deleted/cancelled by the user.


class SubtitleSegment(BaseModel):
    """
    A single timed subtitle segment produced by the transcription service
    and progressively enriched by translation and TTS.
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., description="1-based sequential segment number.")
    start: float = Field(..., ge=0.0, description="Segment start time in seconds.")
    end: float = Field(..., ge=0.0, description="Segment end time in seconds.")
    text: str = Field(..., description="Original transcribed text.")
    translated_text: Optional[str] = Field(
        default=None, description="Translated text in the target language."
    )
    tts_audio_path: Optional[str] = Field(
        default=None, description="Filesystem path to this segment's synthesized audio clip."
    )

    @property
    def duration(self) -> float:
        """Returns the segment duration in seconds."""
        return max(0.0, self.end - self.start)


class DubbingTask(BaseModel):
    """
    Represents one end-to-end video dubbing job, from the moment a video
    is uploaded until the final dubbed video is downloaded or the task
    expires and is cleaned up.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity & lifecycle
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    stage: PipelineStage = PipelineStage.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    message: str = Field(default="Task created.")
    error_message: Optional[str] = None

    # Language / voice configuration
    source_language: Optional[str] = Field(
        default=None, description="ISO language code of the source audio, or None for auto-detect."
    )
    target_language: Optional[str] = Field(
        default=None, description="ISO language code to dub the video into."
    )
    detected_language: Optional[str] = Field(
        default=None, description="Language auto-detected by the transcription service."
    )
    voice: Optional[str] = Field(
        default=None, description="Edge TTS voice name used for synthesis."
    )

    # File references (absolute filesystem paths as strings for JSON safety)
    original_filename: str
    video_path: str
    extracted_audio_path: Optional[str] = None
    silent_video_path: Optional[str] = None
    dubbed_audio_path: Optional[str] = None
    output_video_path: Optional[str] = None
    subtitle_path_original: Optional[str] = None
    subtitle_path_translated: Optional[str] = None

    # Transcript / subtitle data
    segments: List[SubtitleSegment] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(hours=24)
    )

    def touch(self) -> None:
        """Updates the `updated_at` timestamp to the current time."""
        self.updated_at = utc_now()

    def is_expired(self) -> bool:
        """Returns True if this task has passed its expiry time."""
        return utc_now() >= self.expires_at

    def mark_failed(self, error_message: str) -> None:
        """Marks the task as failed with a human-readable error message."""
        self.status = TaskStatus.FAILED
        self.stage = PipelineStage.FAILED
        self.error_message = error_message
        self.message = f"Task failed: {error_message}"
        self.touch()

    def mark_completed(self) -> None:
        """Marks the task as successfully completed."""
        self.status = TaskStatus.COMPLETED
        self.stage = PipelineStage.COMPLETED
        self.progress = 100
        self.message = "Dubbing completed successfully."
        self.touch()

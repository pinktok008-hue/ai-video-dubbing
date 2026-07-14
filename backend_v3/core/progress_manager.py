"""
core/progress_manager.py
===========================
Provides a single, consistent way for the pipeline and its services to
report progress on a `DubbingTask` as it moves through each
`PipelineStage`. Centralizing this logic means the percentage-per-stage
mapping and status transitions live in exactly one place.

Python: 3.12
"""

from __future__ import annotations

from typing import Optional

from config import PipelineStage
from core.logger import get_logger
from core.task_manager import TaskManager
from models.task import DubbingTask, TaskStatus

logger = get_logger(__name__)


class ProgressManager:
    """Updates a task's stage, progress percentage, and status message."""

    def __init__(self, task_manager: TaskManager) -> None:
        self._task_manager = task_manager

    async def update(
        self,
        task_id: str,
        stage: PipelineStage,
        message: Optional[str] = None,
        status_override: Optional[TaskStatus] = None,
    ) -> DubbingTask:
        """
        Advances a task to a new pipeline stage, recomputing its progress
        percentage and persisting the change.

        Args:
            task_id: The task to update.
            stage: The pipeline stage the task has just entered.
            message: Optional human-readable status message. If omitted, a
                sensible default is derived from the stage name.
            status_override: Optional explicit `TaskStatus` to set. If
                omitted, PROCESSING is used for all non-terminal stages.

        Returns:
            The updated `DubbingTask`.
        """
        task = await self._task_manager.require_task(task_id)

        task.stage = stage
        task.progress = PipelineStage.progress_percentage(stage)
        task.message = message or self._default_message(stage)

        if status_override is not None:
            task.status = status_override
        elif stage == PipelineStage.COMPLETED:
            task.status = TaskStatus.COMPLETED
        elif stage == PipelineStage.FAILED:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PROCESSING

        await self._task_manager.update_task(task)
        logger.info("Task %s -> stage=%s progress=%s%%", task_id, stage.value, task.progress)
        return task

    @staticmethod
    def _default_message(stage: PipelineStage) -> str:
        """Returns a human-friendly default message for a given stage."""
        messages = {
            PipelineStage.QUEUED: "Task queued for processing.",
            PipelineStage.UPLOAD: "Video uploaded successfully.",
            PipelineStage.AUDIO_EXTRACTION: "Extracting audio from video.",
            PipelineStage.TRANSCRIPTION: "Transcribing speech to text.",
            PipelineStage.TRANSLATION: "Translating transcript.",
            PipelineStage.SUBTITLE_GENERATION: "Generating subtitle files.",
            PipelineStage.TTS_GENERATION: "Synthesizing dubbed speech.",
            PipelineStage.AUDIO_CLEANUP: "Removing original audio track.",
            PipelineStage.AUDIO_MERGE: "Merging dubbed audio with video.",
            PipelineStage.FINALIZING: "Finalizing output video.",
            PipelineStage.COMPLETED: "Dubbing completed successfully.",
            PipelineStage.FAILED: "Dubbing failed.",
        }
        return messages.get(stage, "Processing.")

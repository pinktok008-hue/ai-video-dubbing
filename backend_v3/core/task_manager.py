"""
core/task_manager.py
=======================
In-memory, async-safe registry of every `DubbingTask` the platform is
tracking. Provides atomic create/read/update/delete operations guarded by
an `asyncio.Lock`, plus a background scheduler that periodically purges
expired tasks and their on-disk files.

For a single-process deployment (Render web service, Docker container)
an in-memory store is sufficient and avoids adding a database dependency
for V3.0. If horizontal scaling is required later, this class can be
swapped for a Redis-backed implementation without touching any other
module, since all access goes through this one interface.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from config import Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from models.task import DubbingTask, TaskStatus

logger = get_logger(__name__)


class TaskManager:
    """Thread/async-safe in-memory store of all `DubbingTask` objects."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._tasks: Dict[str, DubbingTask] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------
    async def add_task(self, task: DubbingTask) -> DubbingTask:
        """Registers a new task in the store."""
        async with self._lock:
            self._tasks[task.task_id] = task
        logger.info("Task registered: %s", task.task_id)
        return task

    async def get_task(self, task_id: str) -> Optional[DubbingTask]:
        """Returns the task with the given ID, or None if it does not exist."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def require_task(self, task_id: str) -> DubbingTask:
        """
        Returns the task with the given ID or raises a KeyError if it does
        not exist. Intended for internal pipeline use where a missing task
        is a programming error rather than a normal user-facing 404.
        """
        task = await self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' does not exist.")
        return task

    async def update_task(self, task: DubbingTask) -> DubbingTask:
        """Persists changes made to a `DubbingTask` instance back into the store."""
        task.touch()
        async with self._lock:
            self._tasks[task.task_id] = task
        return task

    async def delete_task(self, task_id: str, file_manager: FileManager) -> bool:
        """
        Removes a task from the in-memory store and deletes all of its
        associated files from disk.

        Args:
            task_id: The task to delete.
            file_manager: Used to remove the task's on-disk artifacts.

        Returns:
            True if the task existed and was deleted, False otherwise.
        """
        async with self._lock:
            existed = self._tasks.pop(task_id, None) is not None

        if existed:
            file_manager.delete_task_files(task_id)
            logger.info("Task deleted: %s", task_id)

        return existed

    async def list_all_tasks(self) -> List[DubbingTask]:
        """Returns a snapshot list of every task currently tracked."""
        async with self._lock:
            return list(self._tasks.values())

    async def count_active_tasks(self) -> int:
        """Returns the number of tasks currently in PENDING/QUEUED/PROCESSING state."""
        active_statuses = {TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.PROCESSING}
        async with self._lock:
            return sum(1 for task in self._tasks.values() if task.status in active_statuses)

    # ------------------------------------------------------------------
    # Expiry & Cleanup
    # ------------------------------------------------------------------
    async def get_expired_task_ids(self) -> List[str]:
        """Returns the IDs of every task whose expiry time has passed."""
        async with self._lock:
            return [task_id for task_id, task in self._tasks.items() if task.is_expired()]

    async def cleanup_expired_tasks(self, file_manager: FileManager) -> int:
        """
        Deletes every expired task and its files.

        Args:
            file_manager: Used to remove each expired task's on-disk artifacts.

        Returns:
            The number of tasks cleaned up.
        """
        expired_ids = await self.get_expired_task_ids()

        for task_id in expired_ids:
            await self.delete_task(task_id, file_manager)

        if expired_ids:
            logger.info("Cleaned up %s expired task(s).", len(expired_ids))

        return len(expired_ids)

    async def _cleanup_loop(self, file_manager: FileManager) -> None:
        """Background loop that periodically purges expired tasks."""
        interval_seconds = self._settings.TASK_CLEANUP_INTERVAL_MINUTES * 60

        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self.cleanup_expired_tasks(file_manager)
            except asyncio.CancelledError:
                logger.info("Task cleanup loop cancelled.")
                raise
            except Exception as exc:  # noqa: BLE001 - keep the loop alive on unexpected errors
                logger.error("Unexpected error in cleanup loop: %s", exc, exc_info=True)

    def start_cleanup_scheduler(self, file_manager: FileManager) -> None:
        """
        Starts the periodic background cleanup task. Safe to call once
        during application startup (see app.py lifespan handler).
        """
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop(file_manager))
            logger.info(
                "Task cleanup scheduler started (interval=%s minutes, expiry=%s hours).",
                self._settings.TASK_CLEANUP_INTERVAL_MINUTES,
                self._settings.TASK_EXPIRY_HOURS,
            )

    def stop_cleanup_scheduler(self) -> None:
        """Cancels the periodic background cleanup task, if running."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Task cleanup scheduler stopped.")

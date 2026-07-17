"""
core/task_manager.py
=======================
Async-safe registry of every `DubbingTask` the platform is tracking.
Provides atomic create/read/update/delete operations guarded by an
`asyncio.Lock`, plus a background scheduler that periodically purges
expired tasks and their on-disk files.

Sprint 2 (Part 5, resume support): every create/update is also
persisted to a per-task JSON file under `TASK_STATE_DIR`, and
`load_persisted_tasks()` (called once at application startup) reloads
them back into memory. This means a task survives a process restart
within the SAME running container/instance -- e.g. an unhandled crash
that a process supervisor restarts. It does NOT mean a task survives a
platform-level redeploy or Render Free's spin-down-after-inactivity:
both wipe the ephemeral filesystem entirely, which is a deployment
platform constraint no amount of in-app persistence logic can work
around. Combined with `services/pipeline.py`'s per-stage
skip-if-already-done checks, a task that failed partway through (for
any reason short of losing the filesystem) can be safely re-run from
where it left off rather than from scratch.

For a single-process deployment (Render web service, Docker container)
a JSON-file-per-task store is sufficient and avoids adding a database
dependency. If horizontal scaling is required later, this class can be
swapped for a Redis- or Postgres-backed implementation without
touching any other module, since all access goes through this one
interface.

Python: 3.12
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional

from config import Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from models.task import DubbingTask, TaskStatus

logger = get_logger(__name__)


class TaskManager:
    """Async-safe, durably-persisted store of all `DubbingTask` objects."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._tasks: Dict[str, DubbingTask] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Durable Persistence (Sprint 2, Part 5)
    # ------------------------------------------------------------------
    def _task_state_path(self, task_id: str) -> Path:
        return self._settings.TASK_STATE_DIR / f"{task_id}.json"

    def _persist_task_to_disk(self, task: DubbingTask) -> None:
        """
        Writes `task`'s current state to disk. Best-effort: a failure
        here degrades resume support for this one task but must never
        break the in-memory operation that triggered it (the in-memory
        store is always the source of truth for the running process).
        """
        try:
            path = self._task_state_path(task.task_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(task.model_dump(), default=str, indent=2)
            path.write_text(payload, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - persistence must never break a request
            logger.warning("Failed to persist task '%s' to disk: %s", task.task_id, exc, exc_info=True)

    def _remove_persisted_task(self, task_id: str) -> None:
        try:
            self._task_state_path(task_id).unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to remove persisted state for task '%s': %s", task_id, exc, exc_info=True)

    async def load_persisted_tasks(self) -> int:
        """
        Reloads every task JSON file under `TASK_STATE_DIR` into memory.
        Intended to be called once during application startup (see
        app.py's lifespan handler), before the cleanup scheduler starts,
        so a restarted process picks up exactly where it left off.

        Returns:
            The number of tasks successfully reloaded. A single
            corrupt/unreadable task file is logged and skipped rather
            than aborting the whole startup sequence.
        """
        state_dir = self._settings.TASK_STATE_DIR
        if not state_dir.is_dir():
            return 0

        loaded = 0
        async with self._lock:
            for state_file in sorted(state_dir.glob("*.json")):
                try:
                    raw = json.loads(state_file.read_text(encoding="utf-8"))
                    task = DubbingTask(**raw)
                    self._tasks[task.task_id] = task
                    loaded += 1
                except Exception as exc:  # noqa: BLE001 - one bad file must not block the rest
                    logger.error(
                        "Skipping unreadable persisted task file '%s': %s", state_file, exc, exc_info=True
                    )

        if loaded:
            logger.info("Reloaded %s persisted task(s) from disk on startup.", loaded)
        return loaded

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------
    async def add_task(self, task: DubbingTask) -> DubbingTask:
        """Registers a new task in the store and persists it to disk."""
        async with self._lock:
            self._tasks[task.task_id] = task
        self._persist_task_to_disk(task)
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
        """Persists changes made to a `DubbingTask` instance back into the store and to disk."""
        task.touch()
        async with self._lock:
            self._tasks[task.task_id] = task
        self._persist_task_to_disk(task)
        return task

    async def delete_task(self, task_id: str, file_manager: FileManager) -> bool:
        """
        Removes a task from the store (memory and disk) and deletes all
        of its associated media files.

        Args:
            task_id: The task to delete.
            file_manager: Used to remove the task's on-disk artifacts.

        Returns:
            True if the task existed and was deleted, False otherwise.
        """
        async with self._lock:
            existed = self._tasks.pop(task_id, None) is not None

        if existed:
            self._remove_persisted_task(task_id)
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

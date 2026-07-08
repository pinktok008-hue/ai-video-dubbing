"""
core/utils.py
==============
Shared, dependency-free utility functions used across the platform:
task ID generation, filename sanitation, timestamp formatting for
subtitles, async subprocess execution helpers, and misc formatting
helpers.

Python: 3.12
"""

from __future__ import annotations

import asyncio
import re
import secrets
import string
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------
# Identifiers & Timestamps
# --------------------------------------------------------------------------
def generate_task_id(length: int = 12) -> str:
    """
    Generates a URL-safe, unique task identifier composed of lowercase
    letters and digits (e.g. 'a1b2c3d4e5f6').

    Args:
        length: Number of characters in the generated ID.

    Returns:
        A random task ID string.
    """
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def utc_now() -> datetime:
    """Returns the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Filenames
# --------------------------------------------------------------------------
def sanitize_filename(filename: str) -> str:
    """
    Strips directory components, normalizes unicode, and removes any
    character that is not alphanumeric, a dash, underscore, or dot, so the
    resulting string is always safe to use as a filesystem path segment.

    Args:
        filename: The raw, user-supplied filename.

    Returns:
        A sanitized filename safe for filesystem use.
    """
    base_name = Path(filename).name
    normalized = unicodedata.normalize("NFKD", base_name).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", normalized).strip("._")
    return cleaned or "file"


def get_file_extension(filename: str) -> str:
    """Returns the lowercase file extension (including the leading dot)."""
    return Path(filename).suffix.lower()


def human_readable_size(num_bytes: int) -> str:
    """
    Converts a byte count into a human-readable string (e.g. '12.4 MB').

    Args:
        num_bytes: Size in bytes.

    Returns:
        Human-readable size string.
    """
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


# --------------------------------------------------------------------------
# Subtitle Timestamp Formatting
# --------------------------------------------------------------------------
def format_timestamp_srt(seconds: float) -> str:
    """
    Formats a duration in seconds into the SRT timestamp format:
    HH:MM:SS,mmm

    Args:
        seconds: Elapsed time in seconds (can be fractional).

    Returns:
        A string formatted as 'HH:MM:SS,mmm'.
    """
    if seconds < 0:
        seconds = 0.0

    total_milliseconds = int(round(seconds * 1000))
    hours, remainder_ms = divmod(total_milliseconds, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, milliseconds = divmod(remainder_ms, 1_000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def seconds_to_ms(seconds: float) -> int:
    """Converts seconds (float) to whole milliseconds (int), never negative."""
    return max(0, int(round(seconds * 1000)))


# --------------------------------------------------------------------------
# Async Subprocess Execution
# --------------------------------------------------------------------------
async def run_command(command: List[str], timeout_seconds: int) -> Tuple[int, str, str]:
    """
    Executes an external command (e.g. ffmpeg, ffprobe) asynchronously
    without blocking the FastAPI event loop.

    Args:
        command: The full command as a list of argument strings.
        timeout_seconds: Maximum time to allow the command to run before
            it is forcibly killed.

    Returns:
        A tuple of (return_code, stdout_text, stderr_text).

    Raises:
        asyncio.TimeoutError: If the command exceeds `timeout_seconds`.
        FileNotFoundError: If the executable in `command[0]` cannot be found.
    """
    logger.debug("Executing command: %s", " ".join(command))

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error("Command timed out after %s seconds: %s", timeout_seconds, " ".join(command))
        with _suppress_process_errors():
            process.kill()
            await process.wait()
        raise

    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    return_code = process.returncode if process.returncode is not None else -1

    if return_code != 0:
        logger.warning(
            "Command exited with non-zero code %s: %s\nSTDERR: %s",
            return_code,
            " ".join(command),
            stderr_text[-2000:],
        )

    return return_code, stdout_text, stderr_text


class _suppress_process_errors:
    """Small context manager to safely kill a subprocess without raising."""

    def __enter__(self) -> "_suppress_process_errors":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return True


# --------------------------------------------------------------------------
# Retry Helper
# --------------------------------------------------------------------------
async def retry_async(
    coroutine_factory,
    max_retries: int,
    backoff_seconds: float,
    exceptions: Tuple[type, ...] = (Exception,),
):
    """
    Retries an async operation with linear backoff.

    Args:
        coroutine_factory: A zero-argument callable that returns a fresh
            coroutine each time it is invoked (needed because a coroutine
            object can only be awaited once).
        max_retries: Maximum number of attempts before giving up.
        backoff_seconds: Base delay multiplied by the attempt number
            between retries.
        exceptions: Exception types that should trigger a retry.

    Returns:
        The result of the successful coroutine call.

    Raises:
        The last exception encountered if all retries are exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await coroutine_factory()
        except exceptions as exc:  # type: ignore[misc]
            last_exception = exc
            logger.warning(
                "Attempt %s/%s failed with error: %s", attempt, max_retries, exc
            )
            if attempt < max_retries:
                await asyncio.sleep(backoff_seconds * attempt)

    assert last_exception is not None
    raise last_exception

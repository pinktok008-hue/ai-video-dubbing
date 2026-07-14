"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/cache.py

Description:
    Optional caching hook for synthesized TTS clips. `NullTTSCache` --
    the default wired into `TTSEngineManager` -- always misses, so
    caching is a strict no-op out of the box. A real backend (disk,
    Redis, S3, ...) can be dropped in later by implementing `get()`
    and `set()` and passing an instance to
    `TTSEngineManager(cache=...)`, with zero changes anywhere else in
    the TTS stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TTSCacheBackend(Protocol):
    """Interface any TTS cache backend must implement."""

    async def get(self, cache_key: str) -> Optional[Path]:
        """Returns a path to a previously-cached audio clip, or None on a cache miss."""
        ...  # pragma: no cover - Protocol method

    async def set(self, cache_key: str, audio_path: Path) -> None:
        """Stores an audio clip against `cache_key` for future reuse."""
        ...  # pragma: no cover - Protocol method


class NullTTSCache:
    """Default no-op cache backend: every `get` misses, `set` is a no-op."""

    async def get(self, cache_key: str) -> Optional[Path]:
        return None

    async def set(self, cache_key: str, audio_path: Path) -> None:
        return None

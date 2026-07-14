"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/manager.py

Description:
    Ties the engine registry (services/tts/engines) together into a
    single entry point: resolves a requested engine name to a
    lazily-constructed, cached engine instance, runs synthesis through
    it, and transparently walks a configurable, ORDERED fallback chain
    (`Settings.FALLBACK_TTS_ENGINES`) if the primary engine fails, is
    unavailable, or is not configured -- skipping each unavailable
    engine in turn and continuing to the next configured fallback.
    Also exposes engine listing/health-check for the GET /tts/engines
    API endpoint, and an optional caching hook (see cache.py).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from config import Settings, settings
from .base import BaseTTSEngine, TTSRequest, TTSResponse
from .cache import NullTTSCache, TTSCacheBackend
from .engines import get_engine_class, get_registered_engines
from .exceptions import AllTTSEnginesFailedError, TTSEngineError, TTSValidationError

logger = logging.getLogger(__name__)


class EngineHealth:
    """Snapshot of one engine's registration, live health, capabilities, and fallback rank."""

    __slots__ = (
        "name",
        "available",
        "detail",
        "fallback_rank",
        "supports_voice_selection",
        "supports_voice_cloning",
        "supports_streaming",
        "supports_multi_speaker",
    )

    def __init__(
        self, name: str, available: bool, detail: str, fallback_rank: Optional[int], engine: BaseTTSEngine
    ) -> None:
        self.name = name
        self.available = available
        self.detail = detail
        self.fallback_rank = fallback_rank
        self.supports_voice_selection = engine.supports_voice_selection()
        self.supports_voice_cloning = engine.supports_voice_cloning()
        self.supports_streaming = engine.supports_streaming()
        self.supports_multi_speaker = engine.supports_multi_speaker()


class TTSEngineManager:
    """Resolves, caches, and calls TTS engines by name, with a configurable ordered fallback chain."""

    def __init__(self, app_settings: Settings = settings, cache: Optional[TTSCacheBackend] = None) -> None:
        self._settings = app_settings
        self._cache: TTSCacheBackend = cache or NullTTSCache()
        self._instances: Dict[str, BaseTTSEngine] = {}
        self._initialized: Dict[str, bool] = {}

    @property
    def default_engine_name(self) -> str:
        return self._settings.DEFAULT_TTS_ENGINE

    @property
    def fallback_engines(self) -> List[str]:
        """The configured ordered fallback chain, e.g. ['edge', 'azure', 'piper', 'xtts', 'elevenlabs']."""
        return self._settings.get_fallback_engines()

    def _get_or_create_instance(self, engine_name: str) -> BaseTTSEngine:
        if engine_name not in self._instances:
            engine_cls = get_engine_class(engine_name)  # raises ValueError if unregistered
            self._instances[engine_name] = engine_cls(app_settings=self._settings)
        return self._instances[engine_name]

    async def _get_ready_engine(self, engine_name: str) -> BaseTTSEngine:
        """Returns a constructed + initialized engine instance, initializing at most once per process."""
        engine = self._get_or_create_instance(engine_name)
        if not self._initialized.get(engine_name, False):
            await engine.initialize()
            self._initialized[engine_name] = True
        return engine

    @staticmethod
    def _cache_key(engine_name: str, request: TTSRequest) -> str:
        digest_input = "|".join([engine_name, request.language, request.voice or "", request.text])
        return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    def _attempt_order(self, primary_name: str) -> List[str]:
        """Primary engine first, then the configured fallback chain, deduplicated (order-preserving)."""
        seen = {primary_name}
        order = [primary_name]
        for name in self.fallback_engines:
            if name not in seen:
                order.append(name)
                seen.add(name)
        return order

    async def synthesize(self, request: TTSRequest, engine_name: Optional[str] = None) -> TTSResponse:
        """
        Synthesizes `request` with the named engine (or the configured
        default), automatically walking the configured
        `FALLBACK_TTS_ENGINES` chain in order -- skipping any engine
        that fails, is unavailable, or is unconfigured -- until one
        succeeds or the chain is exhausted.

        Raises:
            TTSValidationError: Immediately, without attempting any
                fallback, if the request itself is invalid (every
                engine would reject it identically).
            AllTTSEnginesFailedError: If the primary engine and every
                configured fallback engine all fail.
        """
        primary_name = engine_name or self.default_engine_name

        cache_key = self._cache_key(primary_name, request)
        cached_path = await self._cache.get(cache_key)
        if cached_path is not None:
            logger.debug("TTS cache hit for engine=%s key=%s", primary_name, cache_key[:12])
            return TTSResponse(success=True, engine=primary_name, output_path=cached_path, metadata={"cached": True})

        errors: Dict[str, str] = {}
        for position, name in enumerate(self._attempt_order(primary_name)):
            response, error = await self._try_engine(name, request)
            if response is not None and response.success:
                if position > 0:
                    logger.warning(
                        "TTS engine '%s' failed; recovered via fallback engine '%s' (chain position %d).",
                        primary_name, name, position,
                    )
                if response.output_path is not None:
                    await self._cache.set(cache_key, response.output_path)
                return response

            errors[name] = error or "unknown error"
            logger.warning("TTS engine '%s' unavailable/failed (%s); trying next configured engine.", name, errors[name])

        summary = "; ".join(f"{name}: {err}" for name, err in errors.items())
        raise AllTTSEnginesFailedError(f"All configured TTS engines failed for this request -- {summary}")

    async def _try_engine(
        self, engine_name: str, request: TTSRequest
    ) -> Tuple[Optional[TTSResponse], Optional[str]]:
        """Attempts one engine end-to-end, normalizing any failure mode into (None|response, error_text)."""
        try:
            engine = await self._get_ready_engine(engine_name)
        except TTSEngineError as exc:
            return None, str(exc)
        except Exception as exc:  # noqa: BLE001 - an engine's initialize() must never crash the manager
            return None, f"unexpected error initializing engine: {exc}"

        try:
            response = await engine.generate(request)
        except TTSValidationError:
            # A validation failure is a property of the request itself
            # (empty text, zero speed, ...), not of this engine -- every
            # other engine in the chain would fail the same way, so
            # walking the rest of the chain would only produce a
            # confusing compound error. Propagate immediately instead.
            raise
        except Exception as exc:  # noqa: BLE001 - an engine's generate() must never crash the manager
            return None, str(exc)

        if not response.success:
            return response, response.error or "unknown error"
        return response, None

    async def list_engines(self) -> List[EngineHealth]:
        """Returns a live availability/capability/fallback-rank snapshot for every registered engine."""
        fallback_chain = self.fallback_engines
        results: List[EngineHealth] = []
        for name in sorted(get_registered_engines()):
            engine = self._get_or_create_instance(name)
            try:
                healthy = await engine.health_check()
                detail = "ok" if healthy else "unavailable (missing dependency or configuration)"
            except Exception as exc:  # noqa: BLE001 - a broken health check must not break the endpoint
                healthy, detail = False, f"health_check raised: {exc}"
            rank = fallback_chain.index(name) + 1 if name in fallback_chain else None
            results.append(EngineHealth(name=name, available=healthy, detail=detail, fallback_rank=rank, engine=engine))
        return results

"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/engines/edge_engine.py

Description:
    Microsoft Edge TTS engine adapter -- the platform's original
    synthesis engine, now an optional engine (selectable via
    `POST /dub`'s `tts_engine` field, or via `DEFAULT_TTS_ENGINE` /
    `FALLBACK_TTS_ENGINES` in configuration). Its request/retry/timeout
    behavior is an exact port of what shipped in the pre-V3.1
    single-engine `services/tts_service.py`, so selecting "edge"
    produces identical output to every prior release.
"""

from __future__ import annotations

import asyncio
import logging

import edge_tts

from config import Settings, settings
from core.utils import retry_async
from ..base import BaseTTSEngine, TTSRequest, TTSResponse
from ..exceptions import TTSGenerationError

logger = logging.getLogger(__name__)


class EdgeTTSEngine(BaseTTSEngine):
    """Text-to-speech engine backed by Microsoft Edge's neural voices."""

    ENGINE_NAME = "edge"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__()
        self._settings = app_settings

    async def initialize(self) -> None:
        # `edge-tts` is a hard (non-optional) project dependency, so if it
        # were missing this module's top-level import would already have
        # failed at process startup -- there is nothing left to verify here.
        self.initialized = True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        self.validate_request(request)

        rate = str(request.metadata.get("rate", self._settings.EDGE_TTS_DEFAULT_RATE))
        volume = str(request.metadata.get("volume", self._settings.EDGE_TTS_DEFAULT_VOLUME))
        pitch = str(request.metadata.get("pitch", self._settings.EDGE_TTS_DEFAULT_PITCH))
        voice = request.voice or Settings.get_default_voice(request.language)

        logger.debug(
            "Edge TTS generate(): language=%s requested_voice=%s resolved_voice=%s "
            "rate=%s volume=%s pitch=%s max_retries=%s timeout=%ss",
            request.language, request.voice, voice, rate, volume, pitch,
            self._settings.EDGE_TTS_MAX_RETRIES, self._settings.EDGE_TTS_TIMEOUT_SECONDS,
        )

        async def _attempt() -> str:
            # NOTE: `edge_tts.Communicate` wraps a single-use network stream.
            # Once `.save()` has been called on an instance, that instance
            # cannot be reused -- calling `.save()` on it again raises
            # "stream can only be called once". Because `retry_async` may
            # invoke this coroutine factory multiple times, a brand new
            # `Communicate` instance MUST be constructed on every attempt
            # (including retries). Never hoist this construction outside
            # of `_attempt()` or share one instance across calls.
            communicator = edge_tts.Communicate(
                text=request.text,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
            )
            await asyncio.wait_for(
                communicator.save(str(request.output_path)),
                timeout=self._settings.EDGE_TTS_TIMEOUT_SECONDS,
            )
            if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
                raise TTSGenerationError(
                    f"Edge TTS produced an empty file for text: '{request.text[:60]}...'"
                )
            return str(request.output_path)

        try:
            await retry_async(
                coroutine_factory=_attempt,
                max_retries=self._settings.EDGE_TTS_MAX_RETRIES,
                backoff_seconds=1.5,
                exceptions=(Exception,),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Edge TTS synthesis failed after %d attempt(s): %s: %s "
                "(language=%s, requested_voice=%s, resolved_voice=%s, rate=%s, volume=%s, pitch=%s)",
                self._settings.EDGE_TTS_MAX_RETRIES, type(exc).__name__, exc,
                request.language, request.voice, voice, rate, volume, pitch,
                exc_info=True,
            )
            return TTSResponse(success=False, engine=self.name, error=str(exc))

        return TTSResponse(
            success=True,
            engine=self.name,
            output_path=request.output_path,
            metadata={"voice": voice},
        )

    async def synthesize_stream(self, request: TTSRequest):
        """
        True incremental streaming via `edge_tts.Communicate.stream()`,
        which yields dicts of `{"type": "audio"|"WordBoundary", ...}` as
        Microsoft's endpoint generates them. Only "audio" chunks'
        `data` bytes are yielded here; word-boundary metadata (useful
        for future karaoke-style subtitle highlighting) is dropped.
        """
        voice = request.voice or Settings.get_default_voice(request.language)
        communicator = edge_tts.Communicate(text=request.text, voice=voice)
        async for chunk in communicator.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                yield chunk["data"]

    async def health_check(self) -> bool:
        # Edge TTS has no key/config to verify; the package being
        # importable (guaranteed at process startup, since it is a hard
        # dependency) is the only precondition, so it always reports healthy.
        return True

    def supports_voice_selection(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True

    def supported_languages(self) -> list[str]:
        return []  # Accepts any language present in EDGE_TTS_VOICE_MAP; unmapped codes fall back to English.

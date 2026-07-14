"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/engines/gtts_engine.py

Description:
    Google Translate Text-to-Speech (gTTS) engine adapter.

    gTTS is a thin wrapper around the same public endpoint Google
    Translate's "listen" button uses. It requires no API key and no
    account, which is why it is configured as `DEFAULT_TTS_ENGINE`:
    a fresh deployment with zero configuration can still synthesize
    speech immediately. It offers exactly one voice per language, no
    SSML, and noticeably more robotic prosody than the neural engines
    (Edge, Azure, ElevenLabs) -- those remain available as optional,
    explicitly-selectable engines, and as entries in the configurable
    `FALLBACK_TTS_ENGINES` chain.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from config import Settings, settings
from core.utils import retry_async
from ..base import BaseTTSEngine, TTSRequest, TTSResponse
from ..exceptions import TTSEngineUnavailableError, TTSGenerationError

logger = logging.getLogger(__name__)


class GTTSEngine(BaseTTSEngine):
    """Text-to-speech engine backed by the free Google Translate TTS endpoint."""

    ENGINE_NAME = "gtts"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__()
        self._settings = app_settings

    async def initialize(self) -> None:
        """Verifies the optional `gTTS` package is importable."""
        try:
            import gtts  # noqa: F401
        except ImportError as exc:
            raise TTSEngineUnavailableError(
                "The 'gTTS' package is not installed. Install it with "
                "`pip install gTTS` to enable the gtts engine."
            ) from exc
        self.initialized = True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        self.validate_request(request)

        async def _attempt() -> Path:
            return await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, request),
                timeout=self._settings.GTTS_TIMEOUT_SECONDS,
            )

        try:
            await retry_async(
                coroutine_factory=_attempt,
                max_retries=self._settings.GTTS_MAX_RETRIES,
                backoff_seconds=1.5,
                exceptions=(Exception,),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("gTTS synthesis failed for language '%s': %s", request.language, exc)
            return TTSResponse(success=False, engine=self.name, error=str(exc))

        return TTSResponse(
            success=True,
            engine=self.name,
            output_path=request.output_path,
            metadata={"tld": self._settings.GTTS_DEFAULT_TLD, "slow": self._settings.GTTS_SLOW},
        )

    def _synthesize_sync(self, request: TTSRequest) -> Path:
        """Blocking gTTS call, executed inside a worker thread."""
        from gtts import gTTS  # Imported lazily; see `initialize()`.

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        tts = gTTS(
            text=request.text,
            lang=request.language,
            tld=self._settings.GTTS_DEFAULT_TLD,
            slow=self._settings.GTTS_SLOW,
        )
        tts.save(str(request.output_path))

        if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
            raise TTSGenerationError(f"gTTS produced an empty file for text: '{request.text[:60]}...'")
        return request.output_path

    async def health_check(self) -> bool:
        try:
            import gtts  # noqa: F401
        except ImportError:
            return False
        return True

    def supported_languages(self) -> list[str]:
        return []  # gTTS supports a broad, Google-defined set; validated at call time.

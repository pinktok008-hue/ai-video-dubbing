"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/engines/xtts_engine.py

Description:
    Coqui XTTS v2 engine adapter -- a heavyweight, self-hosted,
    multilingual voice-cloning TTS model. Requires the `TTS` package
    (pulls in PyTorch); CPU inference works but is slow, a GPU is
    strongly recommended for production latency. Intentionally NOT
    part of the base requirements.txt (see requirements-optional.txt)
    since it is incompatible with Render's free tier. Health checks
    and the fallback manager treat a missing/uninitialized XTTS model
    as a normal, recoverable "engine unavailable" condition rather
    than a startup failure.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional, Sequence

from config import Settings, settings
from ..base import BaseTTSEngine, TTSRequest, TTSResponse
from ..exceptions import TTSEngineUnavailableError, TTSGenerationError

logger = logging.getLogger(__name__)


class XTTSEngine(BaseTTSEngine):
    """Text-to-speech engine backed by a locally-hosted Coqui XTTS v2 model."""

    ENGINE_NAME = "xtts"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__()
        self._settings = app_settings
        self._model: Optional[Any] = None

    def _load_model(self) -> Any:
        """
        Lazily imports Coqui `TTS` and loads the XTTS v2 model exactly
        once per process, caching it on `self._model`. Always called
        from inside a worker thread (never directly on the event loop)
        since both the import and the model load are blocking and can
        take tens of seconds on first use.
        """
        if self._model is not None:
            return self._model

        try:
            from TTS.api import TTS
        except ImportError as exc:
            raise TTSEngineUnavailableError(
                "The 'TTS' (Coqui) package is not installed -- see requirements-optional.txt to "
                "enable the xtts engine. Note this pulls in PyTorch and is not recommended for "
                "memory-constrained deployments."
            ) from exc

        logger.info("Loading XTTS v2 model onto device='%s' (first use only)...", self._settings.XTTS_DEVICE)
        self._model = TTS(self._settings.XTTS_MODEL_NAME).to(self._settings.XTTS_DEVICE)
        return self._model

    async def initialize(self) -> None:
        await asyncio.to_thread(self._load_model)
        self.initialized = True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        self.validate_request(request)

        speaker_wav = request.metadata.get("speaker_wav") or self._settings.XTTS_DEFAULT_SPEAKER_WAV
        if not speaker_wav:
            return TTSResponse(
                success=False,
                engine=self.name,
                error="XTTS requires a reference 'speaker_wav' (in request.metadata or "
                "XTTS_DEFAULT_SPEAKER_WAV) to condition the cloned voice.",
            )

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, request, speaker_wav),
                timeout=self._settings.XTTS_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("XTTS synthesis failed: %s", exc)
            return TTSResponse(success=False, engine=self.name, error=str(exc))

        return TTSResponse(
            success=True,
            engine=self.name,
            output_path=request.output_path,
            metadata={"speaker_wav": speaker_wav},
        )

    def _synthesize_sync(self, request: TTSRequest, speaker_wav: str) -> None:
        model = self._load_model()
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        model.tts_to_file(
            text=request.text,
            speaker_wav=speaker_wav,
            language=request.language,
            file_path=str(request.output_path),
        )
        if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
            raise TTSGenerationError(f"XTTS produced an empty file for text: '{request.text[:60]}...'")

    async def health_check(self) -> bool:
        try:
            import TTS  # noqa: F401
        except ImportError:
            return False
        return True

    def supports_voice_cloning(self) -> bool:
        return True

    async def clone_voice(self, reference_audio_paths: Sequence[Path], voice_name: str) -> str:
        """
        XTTS clones a voice implicitly from a reference clip at
        synthesis time (`speaker_wav`) rather than through a separate
        registration step, so there is no persisted "voice ID" to
        create. `voice_name` is accepted for interface symmetry with
        other engines but is not used. Returns the first reference
        clip's path, which callers can then pass back as
        `TTSRequest.metadata["speaker_wav"]`.
        """
        if not reference_audio_paths:
            raise TTSGenerationError("clone_voice requires at least one reference audio path.")
        return str(reference_audio_paths[0])

    def supported_languages(self) -> list[str]:
        # XTTS v2's documented language set per its public model card at
        # authoring time. Verify against the installed model version if
        # Coqui adds/changes supported languages in a future release.
        return [
            "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl",
            "cs", "ar", "zh-CN", "hu", "ko", "ja", "hi",
        ]

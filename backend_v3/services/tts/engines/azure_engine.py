"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/engines/azure_engine.py

Description:
    Microsoft Azure Cognitive Services (Speech SDK) TTS engine adapter.

    Azure Neural TTS shares its underlying voice catalog with Edge TTS
    (e.g. "en-US-AriaNeural" resolves on both, since Edge's "Read
    Aloud" feature is itself built on Azure's neural voice backend),
    so this engine reuses `Settings.get_default_voice()` as a sensible
    default when the caller does not request a specific voice, while
    still allowing any Azure-specific voice name through
    `request.voice`.

    Requires `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`. The engine
    reports itself unhealthy/unconfigured (rather than raising at
    import or startup time) when they are absent, so `/tts/engines`
    and the fallback manager can route around it cleanly.
"""

from __future__ import annotations

import asyncio
import logging

from config import Settings, settings
from ..base import BaseTTSEngine, TTSRequest, TTSResponse
from ..exceptions import TTSEngineNotConfiguredError, TTSEngineUnavailableError, TTSGenerationError

logger = logging.getLogger(__name__)


class AzureTTSEngine(BaseTTSEngine):
    """Text-to-speech engine backed by Azure Cognitive Services Speech."""

    ENGINE_NAME = "azure"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__()
        self._settings = app_settings

    def _is_configured(self) -> bool:
        return bool(self._settings.AZURE_SPEECH_KEY and self._settings.AZURE_SPEECH_REGION)

    async def initialize(self) -> None:
        try:
            import azure.cognitiveservices.speech  # noqa: F401
        except ImportError as exc:
            raise TTSEngineUnavailableError(
                "The 'azure-cognitiveservices-speech' package is not installed. Install it with "
                "`pip install azure-cognitiveservices-speech` to enable the azure engine."
            ) from exc

        if not self._is_configured():
            raise TTSEngineNotConfiguredError(
                "AZURE_SPEECH_KEY and AZURE_SPEECH_REGION must both be set to use the azure engine."
            )
        self.initialized = True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        self.validate_request(request)

        if not self._is_configured():
            return TTSResponse(
                success=False,
                engine=self.name,
                error="Azure engine is not configured (missing AZURE_SPEECH_KEY / AZURE_SPEECH_REGION).",
            )

        voice = request.voice or Settings.get_default_voice(request.language)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, request, voice),
                timeout=self._settings.AZURE_TTS_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Azure TTS synthesis failed: %s", exc)
            return TTSResponse(success=False, engine=self.name, error=str(exc))

        return TTSResponse(
            success=True, engine=self.name, output_path=request.output_path, metadata={"voice": voice}
        )

    def _synthesize_sync(self, request: TTSRequest, voice: str) -> None:
        """Blocking Azure Speech SDK call, executed inside a worker thread."""
        import azure.cognitiveservices.speech as speechsdk

        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        speech_config = speechsdk.SpeechConfig(
            subscription=self._settings.AZURE_SPEECH_KEY,
            region=self._settings.AZURE_SPEECH_REGION,
        )
        speech_config.speech_synthesis_voice_name = voice
        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(request.output_path))
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        result = synthesizer.speak_text_async(request.text).get()

        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            raise TTSGenerationError(
                f"Azure synthesis canceled: {details.reason} - {details.error_details}"
            )
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise TTSGenerationError(f"Azure synthesis did not complete (reason={result.reason}).")
        if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
            raise TTSGenerationError(f"Azure TTS produced an empty file for text: '{request.text[:60]}...'")

    async def health_check(self) -> bool:
        if not self._is_configured():
            return False
        try:
            import azure.cognitiveservices.speech  # noqa: F401
        except ImportError:
            return False
        return True

    def supports_voice_selection(self) -> bool:
        return True

    def supported_languages(self) -> list[str]:
        return []

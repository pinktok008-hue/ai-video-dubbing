"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/engines/elevenlabs_engine.py

Description:
    ElevenLabs TTS engine adapter, implemented as direct async REST
    calls over `httpx` (already a pinned project dependency) rather
    than pulling in the separate `elevenlabs` SDK, keeping the
    engine's footprint minimal.

    Supports real voice cloning via ElevenLabs' "add voice" endpoint.
    Callers are responsible for ensuring they have the legal right and
    the speaker's consent to clone any voice they submit; this engine
    performs no consent verification itself and relies on ElevenLabs'
    own account-level usage policy enforcement.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import httpx

from config import Settings, settings
from ..base import BaseTTSEngine, TTSRequest, TTSResponse
from ..exceptions import TTSEngineNotConfiguredError, TTSGenerationError

logger = logging.getLogger(__name__)

_API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsTTSEngine(BaseTTSEngine):
    """Text-to-speech engine backed by the ElevenLabs REST API."""

    ENGINE_NAME = "elevenlabs"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__()
        self._settings = app_settings

    def _is_configured(self) -> bool:
        return bool(self._settings.ELEVENLABS_API_KEY)

    async def initialize(self) -> None:
        if not self._is_configured():
            raise TTSEngineNotConfiguredError("ELEVENLABS_API_KEY must be set to use the elevenlabs engine.")
        self.initialized = True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        self.validate_request(request)

        if not self._is_configured():
            return TTSResponse(
                success=False,
                engine=self.name,
                error="ElevenLabs engine is not configured (missing ELEVENLABS_API_KEY).",
            )

        voice_id = request.voice or self._settings.ELEVENLABS_DEFAULT_VOICE_ID
        if not voice_id:
            return TTSResponse(
                success=False,
                engine=self.name,
                error="No voice was given and ELEVENLABS_DEFAULT_VOICE_ID is not configured.",
            )

        payload = {
            "text": request.text,
            "model_id": self._settings.ELEVENLABS_MODEL_ID,
            "voice_settings": {
                "stability": self._settings.ELEVENLABS_STABILITY,
                "similarity_boost": self._settings.ELEVENLABS_SIMILARITY_BOOST,
            },
        }
        headers = {"xi-api-key": self._settings.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.ELEVENLABS_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{_API_BASE}/text-to-speech/{voice_id}", json=payload, headers=headers
                )
            if response.status_code != 200:
                raise TTSGenerationError(
                    f"ElevenLabs API returned HTTP {response.status_code}: {response.text[:300]}"
                )

            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_bytes(response.content)

            if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
                raise TTSGenerationError("ElevenLabs API returned an empty audio payload.")
        except httpx.HTTPError as exc:
            logger.error("ElevenLabs request failed: %s", exc)
            return TTSResponse(success=False, engine=self.name, error=str(exc))
        except TTSGenerationError as exc:
            logger.error("ElevenLabs synthesis failed: %s", exc)
            return TTSResponse(success=False, engine=self.name, error=str(exc))

        return TTSResponse(
            success=True, engine=self.name, output_path=request.output_path, metadata={"voice_id": voice_id}
        )

    async def health_check(self) -> bool:
        if not self._is_configured():
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{_API_BASE}/user", headers={"xi-api-key": self._settings.ELEVENLABS_API_KEY}
                )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def supports_voice_selection(self) -> bool:
        return True

    def supports_voice_cloning(self) -> bool:
        return True

    async def clone_voice(self, reference_audio_paths: Sequence[Path], voice_name: str) -> str:
        """
        Uploads one or more reference audio samples to ElevenLabs'
        Instant Voice Cloning endpoint and returns the new `voice_id`,
        which can then be passed as `TTSRequest.voice` on future calls.
        """
        if not self._is_configured():
            raise TTSEngineNotConfiguredError("ELEVENLABS_API_KEY must be set to clone a voice.")
        if not reference_audio_paths:
            raise TTSGenerationError("clone_voice requires at least one reference audio path.")

        files = [
            ("files", (Path(sample_path).name, Path(sample_path).read_bytes(), "audio/mpeg"))
            for sample_path in reference_audio_paths
        ]
        data = {"name": voice_name}
        headers = {"xi-api-key": self._settings.ELEVENLABS_API_KEY}

        async with httpx.AsyncClient(timeout=self._settings.ELEVENLABS_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{_API_BASE}/voices/add", data=data, files=files, headers=headers)

        if response.status_code != 200:
            raise TTSGenerationError(
                f"ElevenLabs voice cloning failed: HTTP {response.status_code}: {response.text[:300]}"
            )

        payload = response.json()
        voice_id = payload.get("voice_id")
        if not voice_id:
            raise TTSGenerationError(f"ElevenLabs voice cloning response was missing 'voice_id': {payload}")
        return voice_id

    def supported_languages(self) -> list[str]:
        return []  # ElevenLabs' multilingual models auto-detect language from the input text.

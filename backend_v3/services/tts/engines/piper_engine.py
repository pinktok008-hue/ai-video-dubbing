"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/engines/piper_engine.py

Description:
    Piper (local, offline neural TTS) engine adapter. Piper runs
    entirely on-device via a standalone binary plus a downloaded
    `.onnx` voice model, so it has zero per-request network dependency
    or API cost -- but the binary and model files are intentionally
    NOT bundled in the default image (see requirements-optional.txt
    and .env.example), since they add real weight to the container.
    Not recommended for Render's free tier; intended for self-hosted
    or dedicated-worker deployments.

    Invoked as a subprocess via `core.utils.run_command` -- the same
    helper this project already uses for every FFmpeg/FFprobe call --
    rather than through Piper's Python API, since the CLI surface
    (text on stdin, `--model` / `--output_file` flags) is the more
    stable, version-independent integration point.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from config import Settings, settings
from core.utils import run_command
from ..base import BaseTTSEngine, TTSRequest, TTSResponse
from ..exceptions import TTSEngineNotConfiguredError, TTSEngineUnavailableError

logger = logging.getLogger(__name__)


class PiperTTSEngine(BaseTTSEngine):
    """Text-to-speech engine backed by a local Piper binary + ONNX voice model."""

    ENGINE_NAME = "piper"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__()
        self._settings = app_settings

    def _binary_available(self) -> bool:
        return shutil.which(self._settings.PIPER_BINARY_PATH) is not None

    def _resolve_model_path(self, request: TTSRequest) -> Optional[Path]:
        override = request.metadata.get("model_path")
        if override:
            return Path(override)
        model_filename = self._settings.PIPER_VOICE_MODEL_MAP.get(request.language)
        if not model_filename:
            return None
        return Path(self._settings.PIPER_MODEL_DIR) / model_filename

    async def initialize(self) -> None:
        if not self._binary_available():
            raise TTSEngineUnavailableError(
                f"Piper binary not found at '{self._settings.PIPER_BINARY_PATH}'. Install Piper "
                "(https://github.com/rhasspy/piper) -- see requirements-optional.txt -- and set "
                "PIPER_BINARY_PATH if it is not on PATH."
            )
        if not self._settings.PIPER_VOICE_MODEL_MAP:
            raise TTSEngineNotConfiguredError(
                "PIPER_VOICE_MODEL_MAP is empty. Configure at least one "
                '`{"<language_code>": "<model>.onnx"}` mapping to use the piper engine.'
            )
        self.initialized = True

    async def generate(self, request: TTSRequest) -> TTSResponse:
        self.validate_request(request)

        if not self._binary_available():
            return TTSResponse(
                success=False,
                engine=self.name,
                error=f"Piper binary not found at '{self._settings.PIPER_BINARY_PATH}'.",
            )

        model_path = self._resolve_model_path(request)
        if model_path is None or not model_path.is_file():
            return TTSResponse(
                success=False,
                engine=self.name,
                error=(
                    f"No Piper voice model configured/found for language '{request.language}' "
                    f"(looked for {model_path})."
                ),
            )

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self._settings.PIPER_BINARY_PATH,
            "--model", str(model_path),
            "--output_file", str(request.output_path),
        ]
        if request.speed and request.speed != 1.0:
            # Piper's length_scale is inverse to speaking rate (>1.0 = slower).
            command += ["--length_scale", f"{1.0 / request.speed:.3f}"]

        try:
            return_code, _stdout, stderr = await run_command(
                command,
                timeout_seconds=self._settings.PIPER_TIMEOUT_SECONDS,
                input_text=request.text,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Piper subprocess failed: %s", exc)
            return TTSResponse(success=False, engine=self.name, error=str(exc))

        if return_code != 0 or not request.output_path.is_file() or request.output_path.stat().st_size == 0:
            return TTSResponse(
                success=False,
                engine=self.name,
                error=f"Piper exited with code {return_code}. Stderr: {stderr[-1000:]}",
            )

        return TTSResponse(
            success=True, engine=self.name, output_path=request.output_path, metadata={"model": str(model_path)}
        )

    async def health_check(self) -> bool:
        return self._binary_available() and bool(self._settings.PIPER_VOICE_MODEL_MAP)

    def supported_languages(self) -> list[str]:
        return list(self._settings.PIPER_VOICE_MODEL_MAP.keys())

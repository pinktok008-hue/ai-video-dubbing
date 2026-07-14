"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/base.py

Description:
    Base interface and shared models for all Text-to-Speech (TTS) engines.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .exceptions import TTSValidationError, UnsupportedLanguageError, VoiceNotFoundError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TTSRequest:
    """
    Standard request object passed to every TTS engine.
    """

    text: str
    language: str
    output_path: Path

    voice: str | None = None
    speaker: str | None = None
    speed: float = 1.0
    pitch: float = 1.0

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TTSResponse:
    """
    Standard response object returned by every TTS engine.
    """

    success: bool
    engine: str

    output_path: Path | None = None
    duration: float | None = None
    error: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTTSEngine(ABC):
    """
    Abstract base class for every TTS engine implementation.
    """

    ENGINE_NAME: str = "base"

    def __init__(self) -> None:
        self.initialized: bool = False

    @property
    def name(self) -> str:
        """Return the registered engine name."""
        return self.ENGINE_NAME

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize engine resources.
        """

    @abstractmethod
    async def generate(self, request: TTSRequest) -> TTSResponse:
        """
        Generate speech from text.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Return True when the engine is healthy and available.
        """

    async def shutdown(self) -> None:
        """
        Optional cleanup hook.
        """
        logger.debug("Shutting down TTS engine '%s'.", self.name)

    def supports_voice_selection(self) -> bool:
        return False

    def supports_voice_cloning(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return False

    def supports_multi_speaker(self) -> bool:
        return False

    async def clone_voice(self, reference_audio_paths: Sequence[Path], voice_name: str) -> str:
        """
        Registers a new cloned voice from one or more reference audio
        samples and returns an engine-specific voice identifier that
        can subsequently be passed as `TTSRequest.voice`.

        Only meaningful when `supports_voice_cloning()` is True; engines
        that don't support cloning inherit this default, which simply
        refuses rather than pretending to succeed.
        """
        raise NotImplementedError(f"Engine '{self.name}' does not support voice cloning.")

    async def synthesize_stream(self, request: "TTSRequest"):
        """
        Yields raw audio bytes incrementally as they become available,
        for engines with true streaming synthesis APIs.

        Only meaningful when `supports_streaming()` is True; engines
        that don't support streaming inherit this default.
        """
        raise NotImplementedError(f"Engine '{self.name}' does not support streaming synthesis.")
        yield b""  # pragma: no cover - unreachable; makes this an async generator by signature.

    def supported_languages(self) -> list[str]:
        """
        Return supported language codes.

        An empty list means the engine accepts any language.
        """
        return []

    def validate_request(self, request: TTSRequest) -> None:
        """
        Validate a synthesis request before processing.
        """

        if not request.text or not request.text.strip():
            raise TTSValidationError("TTS text cannot be empty.")

        if not request.language or not request.language.strip():
            raise TTSValidationError("Language code is required.")

        if request.speed <= 0:
            raise TTSValidationError("Speech speed must be greater than zero.")

        if request.pitch <= 0:
            raise TTSValidationError("Pitch must be greater than zero.")

        supported = self.supported_languages()
        if supported and request.language not in supported:
            raise UnsupportedLanguageError(
                f"Language '{request.language}' is not supported by engine '{self.name}'."
            )

        if request.voice and not self.supports_voice_selection():
            raise VoiceNotFoundError(
                f"Engine '{self.name}' does not support voice selection."
            )

        output_parent = request.output_path.parent
        output_parent.mkdir(parents=True, exist_ok=True)

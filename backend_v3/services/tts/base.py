"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/base.py

Description:
    Base interface for all Text-to-Speech (TTS) engines.

Purpose:
    Every TTS engine (gTTS, Edge, Azure, Piper, XTTS,
    ElevenLabs, etc.) must inherit from BaseTTSEngine.

    This ensures every engine exposes the same API,
    making it possible to switch engines without
    changing the dubbing pipeline.

Author:
    AI Video Dubbing Platform

License:
    Project Internal
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(slots=True)
class TTSRequest:
    """
    Standard request object passed to every TTS engine.
    """

    text: str
    language: str
    output_path: Path

    voice: Optional[str] = None
    speaker: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0

    metadata: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class TTSResponse:
    """
    Standard response returned by every TTS engine.
    """

    success: bool

    engine: str

    output_path: Optional[Path] = None

    duration: Optional[float] = None

    error: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None


class BaseTTSEngine(ABC):
    """
    Abstract base class for all TTS engines.

    Example engines:

        - gTTS
        - Edge TTS
        - Azure Neural Voices
        - Piper
        - XTTS
        - ElevenLabs

    Every implementation must inherit from this class.
    """

    ENGINE_NAME: str = "base"

    def __init__(self) -> None:
        self.initialized = False

    @property
    def name(self) -> str:
        """
        Returns engine name.
        """
        return self.ENGINE_NAME

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize engine resources.

        Called once during application startup if needed.
        """

    @abstractmethod
    async def generate(
        self,
        request: TTSRequest,
    ) -> TTSResponse:
        """
        Generate speech.

        Parameters
        ----------
        request:
            Standard TTS request.

        Returns
        -------
        TTSResponse
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Returns True if the engine is available.
        """

    async def shutdown(self) -> None:
        """
        Optional cleanup hook.

        Engines that allocate resources may override this.
        """
        return

    def supports_voice_selection(self) -> bool:
        """
        Returns whether the engine supports
        selecting different voices.
        """
        return False

    def supports_voice_cloning(self) -> bool:
        """
        Returns whether the engine supports
        voice cloning.
        """
        return False

    def supports_streaming(self) -> bool:
        """
        Returns whether streaming synthesis
        is supported.
        """
        return False

    def supports_multi_speaker(self) -> bool:
        """
        Returns whether the engine supports
        multiple speakers.
        """
        return False

    def supported_languages(self) -> list[str]:
        """
        Returns supported language codes.

        Override in subclasses if applicable.
        """
        return []

    def validate_request(
        self,
        request: TTSRequest,
    ) -> None:
        """
        Performs common validation before synthesis.
        """

        if not request.text:
            raise ValueError("TTS text cannot be empty.")

        if not request.language:
            raise ValueError("Language code is required.")

        if request.speed <= 0:
            raise ValueError("Speech speed must be greater than zero.")

        if request.pitch <= 0:
            raise ValueError("Pitch must be greater than zero.")

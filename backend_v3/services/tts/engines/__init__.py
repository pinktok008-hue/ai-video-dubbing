"""
AI Video Dubbing Platform V3.1 LTS

File:
    backend_v3/services/tts/engines/__init__.py

Description:
    Central registry for all supported Text-to-Speech (TTS) engines.

The TTS manager imports engines exclusively through this module.
Adding a new engine should require only:
    1. Creating a new engine implementation.
    2. Importing and registering it below.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .azure_engine import AzureTTSEngine
from .edge_engine import EdgeTTSEngine
from .elevenlabs_engine import ElevenLabsTTSEngine
from .gtts_engine import GTTSEngine
from .piper_engine import PiperTTSEngine
from .xtts_engine import XTTSEngine

if TYPE_CHECKING:
    from ..base import BaseTTSEngine

logger = logging.getLogger(__name__)

ENGINE_REGISTRY: dict[str, type["BaseTTSEngine"]] = {
    GTTSEngine.ENGINE_NAME: GTTSEngine,
    EdgeTTSEngine.ENGINE_NAME: EdgeTTSEngine,
    AzureTTSEngine.ENGINE_NAME: AzureTTSEngine,
    PiperTTSEngine.ENGINE_NAME: PiperTTSEngine,
    XTTSEngine.ENGINE_NAME: XTTSEngine,
    ElevenLabsTTSEngine.ENGINE_NAME: ElevenLabsTTSEngine,
}


def get_registered_engines() -> dict[str, type["BaseTTSEngine"]]:
    """
    Return a shallow copy of the registered engine mapping.
    """
    return ENGINE_REGISTRY.copy()


def get_engine_class(engine_name: str) -> type["BaseTTSEngine"]:
    """
    Retrieve the registered engine class.

    Raises:
        ValueError: If the requested engine is not registered.
    """
    try:
        return ENGINE_REGISTRY[engine_name]
    except KeyError as exc:
        logger.error("Unknown TTS engine requested: %s", engine_name)
        available = ", ".join(sorted(ENGINE_REGISTRY))
        raise ValueError(
            f"Unsupported TTS engine '{engine_name}'. "
            f"Available engines: {available}"
        ) from exc


__all__ = [
    "AzureTTSEngine",
    "EdgeTTSEngine",
    "ElevenLabsTTSEngine",
    "ENGINE_REGISTRY",
    "GTTSEngine",
    "PiperTTSEngine",
    "XTTSEngine",
    "get_engine_class",
    "get_registered_engines",
]

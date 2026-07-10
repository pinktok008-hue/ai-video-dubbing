"""
AI Video Dubbing Platform V3.1 LTS

File:
    backend_v3/services/tts/engines/__init__.py

Description:
    TTS Engine Package

This package contains all supported Text-to-Speech engines.

Supported Engines
-----------------
- gTTS (Default / Free)
- Edge TTS
- Azure Neural TTS
- Piper
- XTTS
- ElevenLabs

The TTS Manager imports engines only through this package.
This keeps the rest of the application independent from
individual engine implementations.
"""

from .gtts_engine import GTTSEngine

__all__ = [
    "GTTSEngine",
]

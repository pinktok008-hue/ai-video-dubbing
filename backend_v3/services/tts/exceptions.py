"""
AI Video Dubbing Platform V3.1 LTS

File:
    services/tts/exceptions.py

Description:
    Structured exception hierarchy shared by every TTS engine and the
    engine manager, so callers can catch failures at the right level
    of granularity (a single unhealthy engine vs. every engine
    exhausted) instead of catching bare `Exception`.
"""

from __future__ import annotations


class TTSEngineError(Exception):
    """Base class for every error raised by the TTS subsystem."""


class TTSEngineNotConfiguredError(TTSEngineError):
    """Raised when an engine is selected but is missing required configuration (e.g. an API key)."""


class TTSEngineUnavailableError(TTSEngineError):
    """Raised when an engine's runtime dependency (SDK, binary, or model) is not installed or reachable."""


class TTSGenerationError(TTSEngineError):
    """Raised when an engine's synthesis call itself fails (network error, non-zero exit code, empty output)."""


class TTSValidationError(TTSEngineError, ValueError):
    """
    Raised when a `TTSRequest` fails validation before synthesis is attempted.

    Subclasses `ValueError` so any pre-existing `except ValueError` call
    site keeps working unchanged.
    """


class UnsupportedLanguageError(TTSValidationError):
    """Raised when the requested language is not supported by the selected engine."""


class VoiceNotFoundError(TTSValidationError):
    """Raised when the requested voice is not valid for the selected engine."""


class AllTTSEnginesFailedError(TTSEngineError):
    """Raised by `TTSEngineManager` when both the primary and fallback engine fail."""

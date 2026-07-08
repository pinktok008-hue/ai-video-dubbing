"""
services/transcription_service.py
====================================
Converts extracted audio into a timestamped transcript using the Groq
Whisper API (`whisper-large-v3` by default). Returns a detected source
language plus a list of `SubtitleSegment` objects with start/end times,
ready for translation and subtitle generation.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq

from config import Settings, settings
from core.logger import get_logger
from core.utils import retry_async
from models.task import SubtitleSegment

logger = get_logger(__name__)


class TranscriptionError(Exception):
    """Raised when the Groq Whisper API fails to transcribe audio."""


class TranscriptionService:
    """Speech-to-text transcription backed by the Groq Whisper API."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._client: Optional[Groq] = None

    def _get_client(self) -> Groq:
        """Lazily instantiates the Groq SDK client using the configured API key."""
        if not self._settings.GROQ_API_KEY:
            raise TranscriptionError(
                "GROQ_API_KEY is not configured. Set it in the environment before transcribing."
            )
        if self._client is None:
            self._client = Groq(
                api_key=self._settings.GROQ_API_KEY,
                timeout=self._settings.GROQ_REQUEST_TIMEOUT_SECONDS,
            )
        return self._client

    async def transcribe(
        self, audio_path: str, source_language: Optional[str] = None
    ) -> Tuple[str, List[SubtitleSegment]]:
        """
        Transcribes the audio file at `audio_path` into timed segments.

        Args:
            audio_path: Path to the (already extracted) WAV audio file.
            source_language: Optional ISO language code hint. If omitted,
                Whisper auto-detects the spoken language.

        Returns:
            A tuple of (detected_language_code, list_of_subtitle_segments).

        Raises:
            TranscriptionError: If the API call ultimately fails after
                all configured retries.
        """

        async def _attempt() -> Dict[str, Any]:
            return await asyncio.to_thread(self._call_groq_sync, audio_path, source_language)

        try:
            response_payload = await retry_async(
                coroutine_factory=_attempt,
                max_retries=self._settings.GROQ_MAX_RETRIES,
                backoff_seconds=self._settings.GROQ_RETRY_BACKOFF_SECONDS,
                exceptions=(Exception,),
            )
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"Groq transcription failed: {exc}") from exc

        detected_language = response_payload.get("language") or source_language or "en"
        raw_segments = response_payload.get("segments") or []

        segments: List[SubtitleSegment] = []
        for index, raw_segment in enumerate(raw_segments, start=1):
            text = str(raw_segment.get("text", "")).strip()
            if not text:
                continue
            segments.append(
                SubtitleSegment(
                    index=index,
                    start=float(raw_segment.get("start", 0.0)),
                    end=float(raw_segment.get("end", 0.0)),
                    text=text,
                )
            )

        if not segments:
            raise TranscriptionError("Transcription returned no usable speech segments.")

        logger.info(
            "Transcription complete: %s segment(s), detected_language=%s",
            len(segments),
            detected_language,
        )
        return detected_language, segments

    def _call_groq_sync(self, audio_path: str, source_language: Optional[str]) -> Dict[str, Any]:
        """
        Performs the actual (blocking) Groq API call. Executed inside a
        worker thread via `asyncio.to_thread` so it never blocks the
        FastAPI event loop.
        """
        client = self._get_client()

        with open(audio_path, "rb") as audio_file:
            kwargs: Dict[str, Any] = {
                "file": (audio_path, audio_file.read()),
                "model": self._settings.GROQ_WHISPER_MODEL,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"],
            }
            if source_language:
                kwargs["language"] = source_language

            transcription = client.audio.transcriptions.create(**kwargs)

        # The Groq SDK returns a pydantic-like object; normalize to a plain dict.
        if hasattr(transcription, "model_dump"):
            return transcription.model_dump()
        if isinstance(transcription, dict):
            return transcription
        return {
            "language": getattr(transcription, "language", None),
            "segments": getattr(transcription, "segments", []),
            "text": getattr(transcription, "text", ""),
        }

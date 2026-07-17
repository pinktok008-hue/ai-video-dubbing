"""
services/translation_service.py
==================================
Translates each transcribed `SubtitleSegment.text` into the target
language using `deep-translator`'s Google Translate backend. Runs the
synchronous translator calls in worker threads so the FastAPI event loop
is never blocked, with per-segment (per-chunk) retry/backoff for
resilience against transient network errors.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from typing import Dict, List

from deep_translator import GoogleTranslator

from config import Settings, settings
from core.logger import get_logger
from core.utils import retry_async
from models.task import SubtitleSegment

logger = get_logger(__name__)


class TranslationError(Exception):
    """Raised when a segment cannot be translated after all retries."""


# --------------------------------------------------------------------------
# Language Name -> ISO Code Normalization Table
# --------------------------------------------------------------------------
# Speech-recognition and upstream callers may supply either a proper ISO
# language code (e.g. "en", "zh-CN") or a full human-readable language name
# (e.g. "English", "Chinese") -- Groq Whisper in particular returns the
# detected language as a full name rather than a code. deep-translator's
# GoogleTranslator requires a proper code, so every full name it might
# reasonably encounter is normalized here (case-insensitively) before being
# handed to the translator backend.
_LANGUAGE_NAME_TO_CODE: Dict[str, str] = {
    "english": "en",
    "hindi": "hi",
    "bengali": "bn",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh-CN",
    "mandarin": "zh-CN",
    "arabic": "ar",
    "portuguese": "pt",
    "russian": "ru",
    "urdu": "ur",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "gujarati": "gu",
    "punjabi": "pa",
    "kannada": "kn",
    "malayalam": "ml",
    "turkish": "tr",
    "dutch": "nl",
    "polish": "pl",
    "ukrainian": "uk",
    "greek": "el",
    "hebrew": "he",
    "swedish": "sv",
    "finnish": "fi",
    "norwegian": "no",
    "danish": "da",
    "czech": "cs",
    "romanian": "ro",
    "hungarian": "hu",
    "persian": "fa",
    "farsi": "fa",
    "swahili": "sw",
    "malay": "ms",
    "filipino": "fil",
    "tagalog": "fil",
    "vietnamese": "vi",
    "thai": "th",
    "indonesian": "id",
}


class TranslationService:
    """Translates subtitle segments between languages via deep-translator."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def translate_segments(
        self,
        segments: List[SubtitleSegment],
        source_language: str,
        target_language: str,
    ) -> List[SubtitleSegment]:
        """
        Translates every segment's `text` field, populating
        `translated_text` on each `SubtitleSegment` in place.

        Args:
            segments: The transcribed segments to translate.
            source_language: ISO code (or full language name) of the
                detected/source language.
            target_language: ISO code (or full language name) of the
                desired output language.

        Returns:
            The same list of segments, with `translated_text` populated.

        Raises:
            TranslationError: If any segment fails translation after all
                configured retries.
        """
        if source_language == target_language:
            logger.info("Source and target languages match (%s); skipping translation.", target_language)
            for segment in segments:
                segment.translated_text = segment.text
            return segments

        translator_source = self._normalize_language_code(source_language)
        translator_target = self._normalize_language_code(target_language)

        for segment in segments:
            segment.translated_text = await self._translate_single_text(
                text=segment.text,
                source=translator_source,
                target=translator_target,
            )

        logger.info(
            "Translated %s segment(s) from '%s' to '%s'.",
            len(segments),
            source_language,
            target_language,
        )
        return segments

    async def _translate_single_text(self, text: str, source: str, target: str) -> str:
        """Translates one string with retry/backoff, chunking if it is too long."""
        chunks = self._chunk_text(text, self._settings.TRANSLATION_CHUNK_CHAR_LIMIT)
        translated_chunks: List[str] = []

        for chunk in chunks:

            async def _attempt(chunk_text: str = chunk) -> str:
                return await asyncio.to_thread(self._translate_sync, chunk_text, source, target)

            try:
                translated_chunk = await retry_async(
                    coroutine_factory=_attempt,
                    max_retries=self._settings.TRANSLATION_MAX_RETRIES,
                    backoff_seconds=self._settings.TRANSLATION_RETRY_BACKOFF_SECONDS,
                    exceptions=(Exception,),
                )
            except Exception as exc:  # noqa: BLE001
                raise TranslationError(f"Failed to translate text chunk: {exc}") from exc

            translated_chunks.append(translated_chunk)

        return " ".join(translated_chunks)

    def _translate_sync(self, text: str, source: str, target: str) -> str:
        """Blocking call to the deep-translator GoogleTranslator backend."""
        translator = GoogleTranslator(source=source, target=target)
        result = translator.translate(text)
        return result if result else text

    @staticmethod
    def _normalize_language_code(language_code: str) -> str:
        """
        Maps a language code or full language name to the ISO code
        deep-translator's `GoogleTranslator` expects.

        Resolution order:
            1. Empty/None/whitespace-only input -> "auto".
            2. The literal string "auto" (any case) -> "auto".
            3. A recognized full language name (e.g. "English", "Hindi"),
               matched case-insensitively -> its mapped ISO code (e.g.
               "en", "hi").
            4. Anything else is assumed to already be a valid ISO code
               (e.g. "en", "zh-CN", "pt-BR") and is returned unchanged,
               preserving its original casing since region subtags such
               as "zh-CN" are case-sensitive for some backends.

        Args:
            language_code: The raw language code or language name.

        Returns:
            A normalized ISO language code, or "auto" if unspecified.
        """
        if not language_code:
            return "auto"

        stripped = language_code.strip()
        if not stripped:
            return "auto"

        lowered = stripped.lower()
        if lowered == "auto":
            return "auto"

        mapped_code = _LANGUAGE_NAME_TO_CODE.get(lowered)
        if mapped_code is not None:
            return mapped_code

        return stripped

    @staticmethod
    def _chunk_text(text: str, max_chars: int) -> List[str]:
        """
        Splits long text into chunks no longer than `max_chars`, breaking
        on word boundaries where possible so translations stay coherent.

        Args:
            text: The full text to split.
            max_chars: Maximum number of characters allowed per chunk.

        Returns:
            A list of text chunks, each no longer than `max_chars`
            (unless a single word itself exceeds `max_chars`).
        """
        if len(text) <= max_chars:
            return [text]

        words = text.split(" ")
        chunks: List[str] = []
        current_chunk_words: List[str] = []
        current_length = 0

        for word in words:
            projected_length = current_length + len(word) + 1
            if projected_length > max_chars and current_chunk_words:
                chunks.append(" ".join(current_chunk_words))
                current_chunk_words = [word]
                current_length = len(word)
            else:
                current_chunk_words.append(word)
                current_length = projected_length

        if current_chunk_words:
            chunks.append(" ".join(current_chunk_words))

        return chunks

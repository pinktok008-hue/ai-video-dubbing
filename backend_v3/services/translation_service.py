"""
services/translation_service.py
==================================
Translates each transcribed `SubtitleSegment.text` into the target
language using `deep-translator`'s Google Translate backend. Runs the
synchronous translator calls in worker threads so the FastAPI event loop
is never blocked, with per-segment retry/backoff for resilience against
transient network errors.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from typing import List

from deep_translator import GoogleTranslator

from config import Settings, settings
from core.logger import get_logger
from core.utils import retry_async
from models.task import SubtitleSegment

logger = get_logger(__name__)


class TranslationError(Exception):
    """Raised when a segment cannot be translated after all retries."""


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
            source_language: ISO code of the detected/source language.
            target_language: ISO code of the desired output language.

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
    Normalize language names/codes into deep-translator compatible codes.
    """

    if not language_code:
        return "auto"

    language = language_code.strip().lower()

    mapping = {
        "english": "en",
        "en": "en",

        "hindi": "hi",
        "hi": "hi",

        "bengali": "bn",
        "bn": "bn",

        "urdu": "ur",
        "ur": "ur",

        "tamil": "ta",
        "ta": "ta",

        "telugu": "te",
        "te": "te",

        "marathi": "mr",
        "mr": "mr",

        "gujarati": "gu",
        "gu": "gu",

        "kannada": "kn",
        "kn": "kn",

        "malayalam": "ml",
        "ml": "ml",

        "punjabi": "pa",
        "pa": "pa",

        "german": "de",
        "de": "de",

        "french": "fr",
        "fr": "fr",

        "spanish": "es",
        "es": "es",

        "italian": "it",
        "it": "it",

        "portuguese": "pt",
        "pt": "pt",

        "russian": "ru",
        "ru": "ru",

        "japanese": "ja",
        "ja": "ja",

        "korean": "ko",
        "ko": "ko",

        "arabic": "ar",
        "ar": "ar",

        "turkish": "tr",
        "tr": "tr",

        "chinese": "zh-CN",
        "chinese (simplified)": "zh-CN",
        "zh-cn": "zh-CN",

        "auto": "auto",
    }

    return mapping.get(language, language)

    @staticmethod
    def _chunk_text(text: str, max_chars: int) -> List[str]:
        """
        Splits long text into chunks no longer than `max_chars`, breaking
        on sentence/word boundaries where possible so translations stay
        coherent.
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

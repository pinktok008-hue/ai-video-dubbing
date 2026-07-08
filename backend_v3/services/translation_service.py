"""
services/translation_service.py
==================================
Translates subtitle segments using deep-translator.
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
    """Raised when translation fails."""


class TranslationService:
    """Translation service using GoogleTranslator."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def translate_segments(
        self,
        segments: List[SubtitleSegment],
        source_language: str,
        target_language: str,
    ) -> List[SubtitleSegment]:

        if not segments:
            return segments

        source = self._normalize_language_code(source_language)
        target = self._normalize_language_code(target_language)

        logger.info(
            "Translation started: %s -> %s",
            source,
            target,
        )

        if source == target:
            logger.info("Source and target are same. Skipping translation.")
            for segment in segments:
                segment.translated_text = segment.text
            return segments

        for segment in segments:
            translated = await self._translate_single_text(
                text=segment.text,
                source=source,
                target=target,
            )

            segment.translated_text = translated

        logger.info(
            "Translated %d subtitle segments.",
            len(segments),
        )

        return segments
            async def _translate_single_text(
        self,
        text: str,
        source: str,
        target: str,
    ) -> str:
        """
        Translate a single text string.
        """

        chunks = self._chunk_text(
            text,
            self._settings.TRANSLATION_CHUNK_CHAR_LIMIT,
        )

        translated_chunks: List[str] = []

        for chunk in chunks:

            async def _attempt(chunk_text: str = chunk) -> str:
                return await asyncio.to_thread(
                    self._translate_sync,
                    chunk_text,
                    source,
                    target,
                )

            try:
                translated = await retry_async(
                    coroutine_factory=_attempt,
                    max_retries=self._settings.TRANSLATION_MAX_RETRIES,
                    backoff_seconds=self._settings.TRANSLATION_RETRY_BACKOFF_SECONDS,
                    exceptions=(Exception,),
                )

            except Exception as exc:
                raise TranslationError(
                    f"Failed to translate text chunk: {exc}"
                ) from exc

            translated_chunks.append(translated)

        return " ".join(translated_chunks)

    def _translate_sync(
        self,
        text: str,
        source: str,
        target: str,
    ) -> str:
        """
        Blocking Google Translate call.
        """

        translator = GoogleTranslator(
            source=source,
            target=target,
        )

        translated = translator.translate(text)

        return translated if translated else text

    @staticmethod
    def _normalize_language_code(language_code: str) -> str:
        """
        Convert language names into ISO language codes that
        deep-translator supports.
        """

        if not language_code:
            return "auto"

        language = language_code.strip().lower()

        mapping = {

            "auto": "auto",

            "english": "en",
            "en": "en",

            "hindi": "hi",
            "hi": "hi",

            "bengali": "bn",
            "bn": "bn",

            "urdu": "ur",
            "ur": "ur",

            "marathi": "mr",
            "mr": "mr",

            "gujarati": "gu",
            "gu": "gu",

            "punjabi": "pa",
            "pa": "pa",

            "kannada": "kn",
            "kn": "kn",

            "malayalam": "ml",
            "ml": "ml",

            "tamil": "ta",
            "ta": "ta",

            "telugu": "te",
            "te": "te",

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

            "arabic": "ar",
            "ar": "ar",

            "japanese": "ja",
            "ja": "ja",

            "korean": "ko",
            "ko": "ko",

            "turkish": "tr",
            "tr": "tr",

            "chinese": "zh-CN",
            "chinese (simplified)": "zh-CN",
            "zh-cn": "zh-CN",
        }

        return mapping.get(language, language)

    @staticmethod
    def _chunk_text(text: str, max_chars: int) -> List[str]:
        """
        Split long text into smaller chunks while preserving words.
        """

        if not text:
            return [""]

        if len(text) <= max_chars:
            return [text]

        words = text.split()

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for word in words:

            word_length = len(word)

            if current_chunk and (current_length + word_length + 1) > max_chars:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = word_length

            else:
                current_chunk.append(word)

                if current_length == 0:
                    current_length = word_length
                else:
                    current_length += word_length + 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks
        

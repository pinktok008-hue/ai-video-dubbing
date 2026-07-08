"""
services/subtitle_service.py
===============================
Generates industry-standard `.srt` subtitle files from a list of
`SubtitleSegment` objects, for both the original transcript and the
translated transcript.

Python: 3.12
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from config import Settings, settings
from core.logger import get_logger
from core.utils import format_timestamp_srt
from models.task import SubtitleSegment

logger = get_logger(__name__)


class SubtitleGenerationError(Exception):
    """Raised when a subtitle file cannot be written to disk."""


class SubtitleService:
    """Builds `.srt` subtitle files from timed transcript segments."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def generate_srt(
        self,
        segments: List[SubtitleSegment],
        output_path: str,
        use_translated_text: bool,
    ) -> str:
        """
        Writes a `.srt` subtitle file for the given segments.

        Args:
            segments: The subtitle segments to render.
            output_path: Destination path for the `.srt` file.
            use_translated_text: If True, renders `segment.translated_text`;
                otherwise renders the original `segment.text`.

        Returns:
            The `output_path` on success.

        Raises:
            SubtitleGenerationError: If the file cannot be written, or if
                translated text was requested but is missing on a segment.
        """
        if not segments:
            raise SubtitleGenerationError("Cannot generate subtitles from an empty segment list.")

        lines: List[str] = []
        for entry_number, segment in enumerate(segments, start=1):
            text = segment.translated_text if use_translated_text else segment.text
            if use_translated_text and not text:
                raise SubtitleGenerationError(
                    f"Segment {segment.index} is missing translated text required for subtitle generation."
                )

            start_timestamp = format_timestamp_srt(segment.start)
            end_timestamp = format_timestamp_srt(segment.end)

            lines.append(str(entry_number))
            lines.append(f"{start_timestamp} --> {end_timestamp}")
            lines.append(text or "")
            lines.append("")  # Blank line separator between entries.

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            destination.write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            raise SubtitleGenerationError(f"Failed to write subtitle file '{output_path}': {exc}") from exc

        logger.info(
            "Generated %s subtitle file with %s entries -> %s",
            "translated" if use_translated_text else "original",
            len(segments),
            output_path,
        )
        return output_path

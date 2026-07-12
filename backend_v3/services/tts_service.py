"""
services/tts_service.py
==========================

Synthesizes speech for translated subtitle segments using the platform's
modular TTS architecture while remaining backward compatible with the
existing pipeline.

The service delegates speech generation to the configured TTS engine
through the shared abstraction layer and assembles all synthesized clips
into a single synchronized audio track using FFmpeg.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional, Tuple

from config import Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from core.utils import retry_async, run_command, seconds_to_ms
from models.task import SubtitleSegment

from services.tts.base import TTSRequest
from services.tts.manager import TTSManager

logger = get_logger(__name__)


class TTSGenerationError(Exception):
    """Raised when speech synthesis or audio assembly fails."""


class TTSService:
    """
    High-level text-to-speech service.

    This service is intentionally isolated from individual TTS engine
    implementations. Engine selection, fallback, validation and health
    checks are delegated to the TTS manager.
    """

    def __init__(
        self,
        app_settings: Settings = settings,
        manager: Optional[TTSManager] = None,
    ) -> None:
        self._settings = app_settings
        self._manager = manager or TTSManager(app_settings)

    # ------------------------------------------------------------------
    # Per-segment synthesis
    # ------------------------------------------------------------------

    async def synthesize_segment(
        self,
        text: str,
        voice: str,
        output_path: str,
        language: str,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        pitch: Optional[str] = None,
    ) -> str:
        """
        Generate speech for a single subtitle segment.

        Args:
            text:
                Input text.
            voice:
                Voice identifier.
            output_path:
                Destination audio path.
            language:
                Language code.
            rate:
                Optional speaking rate.
            volume:
                Optional volume.
            pitch:
                Optional pitch.

        Returns:
            Generated audio path.
        """

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        request = TTSRequest(
            text=text,
            language=language,
            voice=voice,
            output_path=Path(output_path),
            metadata={
                "rate": rate,
                "volume": volume,
                "pitch": pitch,
            },
        )

        async def _attempt() -> str:
            response = await self._manager.synthesize(request)

            if not response.success:
                raise TTSGenerationError(response.error or "Unknown TTS error.")

            if response.output_path is None:
                raise TTSGenerationError("Engine returned no output path.")

            if (
                not response.output_path.exists()
                or response.output_path.stat().st_size == 0
            ):
                raise TTSGenerationError("Generated audio file is empty.")

            return str(response.output_path)

        try:
            return await retry_async(
                coroutine_factory=_attempt,
                max_retries=self._settings.EDGE_TTS_MAX_RETRIES,
                backoff_seconds=1.5,
                exceptions=(Exception,),
            )

        except Exception as exc:  # noqa: BLE001
            raise TTSGenerationError(
                f"TTS synthesis failed: {exc}"
            ) from exc

    async def synthesize_segments(
        self,
        segments: List[SubtitleSegment],
        voice: str,
        language: str,
        task_id: str,
        file_manager: FileManager,
    ) -> List[Tuple[SubtitleSegment, str]]:
        """
        Generate speech for every translated subtitle segment.
        """

        results: List[Tuple[SubtitleSegment, str]] = []

        for segment in segments:
            text = (segment.translated_text or "").strip()

            if not text:
                logger.warning(
                    "Segment %s has no translated text. Skipping.",
                    segment.index,
                )
                continue

            output_path = str(
                file_manager.get_segment_audio_path(
                    task_id,
                    segment.index,
                )
            )

            generated_path = await self.synthesize_segment(
                text=text,
                voice=voice,
                language=language,
                output_path=output_path,
            )

            segment.tts_audio_path = generated_path

            results.append(
                (
                    segment,
                    generated_path,
                )
            )

        if not results:
            raise TTSGenerationError(
                "No subtitle segments were synthesized successfully."
            )

        logger.info(
            "Synthesized %d subtitle segments.",
            len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Audio assembly
    # ------------------------------------------------------------------

    async def build_dubbed_audio_track(
            self,
        segments_with_audio: List[Tuple[SubtitleSegment, str]],
        total_duration_seconds: float,
        output_path: str,
    ) -> str:
        """
        Assemble synthesized segment clips into a single synchronized
        audio track while preserving the original subtitle timing.

        Args:
            segments_with_audio:
                List of (segment, audio_path) tuples.
            total_duration_seconds:
                Total source video duration.
            output_path:
                Destination audio file.

        Returns:
            Path to the generated audio track.

        Raises:
            TTSGenerationError:
                If FFmpeg fails to assemble the final track.
        """

        if not segments_with_audio:
            raise TTSGenerationError(
                "Cannot assemble audio without synthesized segments."
            )

        Path(output_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_duration = max(
            total_duration_seconds,
            1.0,
        )

        command: list[str] = [
            self._settings.FFMPEG_BINARY,
            "-y",
            "-f",
            "lavfi",
            "-t",
            f"{safe_duration:.3f}",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=24000",
        ]

        for _, clip_path in segments_with_audio:
            command.extend(
                [
                    "-i",
                    clip_path,
                ]
            )

        filter_parts: list[str] = []
        mix_labels: list[str] = ["0:a"]

        for index, (segment, _) in enumerate(
            segments_with_audio,
            start=1,
        ):
            delay_ms = seconds_to_ms(segment.start)

            label = f"a{index}"

            filter_parts.append(
                f"[{index}:a]"
                f"adelay={delay_ms}|{delay_ms}"
                f"[{label}]"
            )

            mix_labels.append(label)

        input_labels = "".join(
            f"[{label}]"
            for label in mix_labels
        )

        filter_parts.append(
            (
                f"{input_labels}"
                f"amix="
                f"inputs={len(mix_labels)}:"
                f"duration=first:"
                f"dropout_transition=0,"
                f"volume={len(mix_labels)}"
                f"[aout]"
            )
        )

        filter_complex = ";".join(filter_parts)

        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[aout]",
                "-t",
                f"{safe_duration:.3f}",
                "-c:a",
                "aac",
                "-b:a",
                self._settings.OUTPUT_AUDIO_BITRATE,
            ]
        )

        if self._settings.FFMPEG_THREADS > 0:
            command.extend(
                [
                    "-threads",
                    str(self._settings.FFMPEG_THREADS),
                ]
            )

        command.append(output_path)

        logger.info(
            "Building dubbed audio track with %d synthesized segment(s).",
            len(segments_with_audio),
        )

        return_code, stdout, stderr = await run_command(
            command,
            timeout_seconds=self._settings.FFMPEG_TIMEOUT_SECONDS,
        )

        if return_code != 0:
            logger.error(
                "FFmpeg audio assembly failed.\nSTDOUT:\n%s\nSTDERR:\n%s",
                stdout,
                stderr,
            )

            raise TTSGenerationError(
                "Failed to assemble dubbed audio track."
            )

        if not Path(output_path).exists():
            raise TTSGenerationError(
                "FFmpeg completed but no output audio file was produced."
            )

        logger.info(
            "Dubbed audio successfully generated: %s",
            output_path,
        )

        return output_path


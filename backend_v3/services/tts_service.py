"""
services/tts_service.py
==========================
Synthesizes speech for each translated subtitle segment using Microsoft
Edge TTS, then assembles the individual segment clips into a single
continuous audio track that preserves each segment's original start time
(so the dubbed speech stays roughly synchronized with on-screen action).

Assembly strategy: a silent base track (`anullsrc`) spanning the full
video duration is generated first, then every segment clip is delayed to
its original timestamp (`adelay`) and mixed on top (`amix`) via a single
FFmpeg `filter_complex` graph. This keeps timing anchored to the source
transcript without requiring per-segment audio stretching.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional, Tuple

import edge_tts

from config import Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from core.utils import retry_async, run_command, seconds_to_ms
from models.task import SubtitleSegment

logger = get_logger(__name__)


class TTSGenerationError(Exception):
    """Raised when speech synthesis or audio track assembly fails."""


class TTSService:
    """Text-to-speech synthesis and timed audio track assembly via Edge TTS."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    # ------------------------------------------------------------------
    # Per-Segment Synthesis
    # ------------------------------------------------------------------
    async def synthesize_segment(
        self,
        text: str,
        voice: str,
        output_path: str,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        pitch: Optional[str] = None,
    ) -> str:
        """
        Synthesizes a single piece of text into an MP3 file using Edge TTS.

        Args:
            text: The text to synthesize.
            voice: The Edge TTS voice name (e.g. 'en-US-AriaNeural').
            output_path: Destination path for the synthesized MP3 clip.
            rate: Speaking rate adjustment (e.g. '+0%').
            volume: Volume adjustment (e.g. '+0%').
            pitch: Pitch adjustment (e.g. '+0Hz').

        Returns:
            The `output_path` on success.

        Raises:
            TTSGenerationError: If synthesis fails after all retries.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        communicator = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate or self._settings.EDGE_TTS_DEFAULT_RATE,
            volume=volume or self._settings.EDGE_TTS_DEFAULT_VOLUME,
            pitch=pitch or self._settings.EDGE_TTS_DEFAULT_PITCH,
        )

        async def _attempt() -> str:
            try:
                await asyncio.wait_for(
                    communicator.save(output_path),
                    timeout=self._settings.EDGE_TTS_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as exc:
                raise TTSGenerationError(
                    f"Edge TTS timed out after {self._settings.EDGE_TTS_TIMEOUT_SECONDS}s "
                    f"for text: '{text[:60]}...'"
                ) from exc
            if not Path(output_path).is_file() or Path(output_path).stat().st_size == 0:
                raise TTSGenerationError(f"Edge TTS produced an empty file for text: '{text[:60]}...'")
            return output_path

        try:
            return await retry_async(
                coroutine_factory=_attempt,
                max_retries=self._settings.EDGE_TTS_MAX_RETRIES,
                backoff_seconds=1.5,
                exceptions=(Exception,),
            )
        except Exception as exc:  # noqa: BLE001
            raise TTSGenerationError(f"Edge TTS synthesis failed: {exc}") from exc

    async def synthesize_segments(
        self,
        segments: List[SubtitleSegment],
        voice: str,
        task_id: str,
        file_manager: FileManager,
    ) -> List[Tuple[SubtitleSegment, str]]:
        """
        Synthesizes every segment's `translated_text` into its own audio
        clip, storing the resulting path on the segment itself.

        Args:
            segments: Segments with `translated_text` already populated.
            voice: The Edge TTS voice name to use for all segments.
            task_id: The owning task's ID (used to namespace clip files).
            file_manager: Used to resolve per-segment output paths.

        Returns:
            A list of (segment, audio_clip_path) tuples, in segment order.

        Raises:
            TTSGenerationError: If any segment fails to synthesize.
        """
        results: List[Tuple[SubtitleSegment, str]] = []

        for segment in segments:
            text = (segment.translated_text or "").strip()
            if not text:
                logger.warning("Segment %s has no translated text; skipping TTS.", segment.index)
                continue

            output_path = str(file_manager.get_segment_audio_path(task_id, segment.index))
            await self.synthesize_segment(text=text, voice=voice, output_path=output_path)

            segment.tts_audio_path = output_path
            results.append((segment, output_path))

        if not results:
            raise TTSGenerationError("No segments were successfully synthesized.")

        logger.info("Synthesized %s TTS segment clip(s) for task %s.", len(results), task_id)
        return results

    # ------------------------------------------------------------------
    # Timed Track Assembly
    # ------------------------------------------------------------------
    async def build_dubbed_audio_track(
        self,
        segments_with_audio: List[Tuple[SubtitleSegment, str]],
        total_duration_seconds: float,
        output_path: str,
    ) -> str:
        """
        Assembles all per-segment TTS clips into one continuous audio
        track, positioning each clip at its original segment start time
        so the dub roughly tracks the source video's timing.

        Args:
            segments_with_audio: (segment, audio_clip_path) tuples, in order.
            total_duration_seconds: Duration of the source video, used to
                size the base silent track and trim the final output.
            output_path: Destination path for the assembled audio track.

        Returns:
            The `output_path` on success.

        Raises:
            TTSGenerationError: If FFmpeg fails to assemble the track.
        """
        if not segments_with_audio:
            raise TTSGenerationError("Cannot build an audio track from zero synthesized segments.")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        safe_duration = max(total_duration_seconds, 1.0)

        command: List[str] = [self._settings.FFMPEG_BINARY, "-y"]

        # Input 0: a full-length silent base track, guaranteeing the final
        # output spans the entire video duration even if the last segment
        # ends before the video does.
        command += [
            "-f", "lavfi",
            "-t", f"{safe_duration:.3f}",
            "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
        ]

        # Inputs 1..N: each synthesized segment clip.
        for _segment, clip_path in segments_with_audio:
            command += ["-i", clip_path]

        filter_parts: List[str] = []
        mix_labels: List[str] = ["0:a"]

        for position, (segment, _clip_path) in enumerate(segments_with_audio, start=1):
            delay_ms = seconds_to_ms(segment.start)
            label = f"a{position}"
            filter_parts.append(f"[{position}:a]adelay={delay_ms}|{delay_ms}[{label}]")
            mix_labels.append(label)

        mix_inputs = "".join(f"[{label}]" for label in mix_labels)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0,"
            f"volume={len(mix_labels)}[aout]"
        )

        filter_complex = ";".join(filter_parts)

        command += [
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-t", f"{safe_duration:.3f}",
            "-c:a", "aac",
            "-b:a", self._settings.OUTPUT_AUDIO_BITRATE,
        ]
        if self._settings.FFMPEG_THREADS > 0:
            command += ["-threads", str(self._settings.FFMPEG_THREADS)]
        command.append(output_path)

        logger.info("Assembling dubbed audio track for %s segment(s) -> %s", len(segments_with_audio), output_path)

        return_code, _stdout, stderr = await run_command(
            command, timeout_seconds=self._settings.FFMPEG_TIMEOUT_SECONDS
        )

        if return_code != 0 or not Path(output_path).is_file():
            raise TTSGenerationError(
                f"Failed to assemble dubbed audio track. FFmpeg stderr: {stderr[-1500:]}"
            )

        logger.info("Dubbed audio track assembly complete: %s", output_path)
        return output_path

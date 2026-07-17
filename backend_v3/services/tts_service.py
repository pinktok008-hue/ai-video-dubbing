"""
services/tts_service.py
==========================
Public facade for text-to-speech synthesis and timed audio track
assembly. Per-segment speech synthesis is delegated to
`services.tts.manager.TTSEngineManager`, which resolves a requested
engine name (gTTS, Edge, Azure, Piper, XTTS, or ElevenLabs) to a
concrete engine implementation and transparently walks the configured
`FALLBACK_TTS_ENGINES` chain, in order, if the requested engine fails
or is unavailable.

Sprint 2 additions:
    - Per-clip DSP (silence trim, fade, loudness normalization, noise
      gate, click reduction) and timeline alignment (bounded
      time-stretch to fit each clip within its segment window) are
      applied via `services.audio_processing.AudioProcessor` after
      each clip is synthesized. Both default to states that reproduce
      pre-Sprint-2 output exactly -- see config.py.
    - Segment synthesis is now bounded-concurrency parallel
      (`TTS_PARALLEL_WORKERS`) rather than strictly sequential, with
      fail-fast semantics preserved: the first segment failure cancels
      any still-in-flight segments and fails the whole call, exactly
      as the prior sequential implementation did.
    - `synthesize_segment` logs the exact exception (with stack trace),
      requested language/voice/engine, and records whether a fallback
      engine was needed, for diagnosing production failures without
      needing to reproduce them first.

`build_dubbed_audio_track` (the FFmpeg-based timed-track assembly
step) is engine-agnostic and unchanged in its core mixing logic from
the platform's original implementation: it only cares about a list of
(segment, clip_path) pairs and never about which engine produced each
clip. Its output can now optionally be passed through
`AudioProcessor.process_final_track` (equalizer/compression/limiter).

This module's public surface -- `synthesize_segment`,
`synthesize_segments`, `build_dubbed_audio_track` -- stays backward
compatible: every new parameter is optional, so `services/pipeline.py`
needed only additional keyword arguments at existing call sites.
Omitting `engine` resolves to whatever `DEFAULT_TTS_ENGINE` is
currently configured (gTTS by default), rather than any one engine
being hardcoded here.

Python: 3.12
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional, Tuple

from config import Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from core.utils import run_command, seconds_to_ms
from models.task import SubtitleSegment
from services.audio_processing import AudioProcessor
from services.tts.base import TTSRequest
from services.tts.engines import get_registered_engines
from services.tts.exceptions import TTSEngineError
from services.tts.manager import EngineHealth, TTSEngineManager

logger = get_logger(__name__)


class TTSGenerationError(Exception):
    """Raised when speech synthesis or audio track assembly fails."""


# Output file extension each engine's native synthesis format uses.
# `FileManager.get_segment_audio_path` accepts an `extension` override
# so segment clip filenames always match what each engine actually writes.
_ENGINE_OUTPUT_EXTENSIONS = {
    "gtts": "mp3",
    "edge": "mp3",
    "azure": "wav",
    "elevenlabs": "mp3",
    "piper": "wav",
    "xtts": "wav",
}
_DEFAULT_OUTPUT_EXTENSION = "mp3"


class TTSService:
    """Text-to-speech synthesis (multi-engine, parallel, DSP-processed) and timed audio track assembly."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._manager = TTSEngineManager(app_settings=app_settings)
        self._audio_processor = AudioProcessor(app_settings=app_settings)

    # ------------------------------------------------------------------
    # Engine Introspection (backs GET /tts/engines)
    # ------------------------------------------------------------------
    def is_engine_registered(self, engine_name: str) -> bool:
        """Returns True if `engine_name` is a known, registered TTS engine."""
        return engine_name in get_registered_engines()

    async def list_engines(self) -> List[EngineHealth]:
        """Returns a live availability/capability snapshot for every registered engine."""
        return await self._manager.list_engines()

    # ------------------------------------------------------------------
    # Per-Segment Synthesis
    # ------------------------------------------------------------------
    async def synthesize_segment(
        self,
        text: str,
        voice: str,
        output_path: str,
        language: str = "en",
        engine: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        pitch: Optional[str] = None,
        task_id: Optional[str] = None,
        segment_index: Optional[int] = None,
    ) -> str:
        """
        Synthesizes a single piece of text into an audio file using the
        requested TTS engine (or `DEFAULT_TTS_ENGINE` if omitted).

        Args:
            text: The text to synthesize.
            voice: Engine-specific voice name/ID. Interpreted by
                whichever engine ultimately handles the request; ignored
                by engines that don't support voice selection (e.g. gTTS).
            output_path: Destination path for the synthesized audio clip.
            language: ISO language code for the text being synthesized.
            engine: Registered engine name (e.g. 'edge', 'gtts', 'azure',
                'piper', 'xtts', 'elevenlabs'). Defaults to `DEFAULT_TTS_ENGINE`.
            rate: Optional Edge-TTS-style speaking rate override (e.g. '+0%').
            volume: Optional Edge-TTS-style volume override (e.g. '+0%').
            pitch: Optional Edge-TTS-style pitch override (e.g. '+0Hz').
            task_id: Optional, logging context only (which task this
                segment belongs to) -- has no effect on synthesis.
            segment_index: Optional, logging context only.

        Returns:
            The `output_path` on success.

        Raises:
            TTSGenerationError: If synthesis fails on both the requested
                engine and every configured fallback engine.
        """
        metadata = {}
        if rate is not None:
            metadata["rate"] = rate
        if volume is not None:
            metadata["volume"] = volume
        if pitch is not None:
            metadata["pitch"] = pitch

        resolved_engine = engine or self._settings.DEFAULT_TTS_ENGINE
        log_context = {"task_id": task_id, "segment_index": segment_index}

        logger.debug(
            "TTS request: task_id=%s segment=%s engine=%s language=%s voice=%s text_preview=%r",
            task_id, segment_index, resolved_engine, language, voice, text[:60],
            extra=log_context,
        )

        request = TTSRequest(
            text=text,
            language=language,
            output_path=Path(output_path),
            voice=voice or None,
            metadata=metadata,
        )

        try:
            response = await self._manager.synthesize(request, engine_name=engine)
        except TTSEngineError as exc:
            # Full stack trace + exact exception, plus every input that
            # determined this call's outcome -- this is the diagnostic
            # detail needed to root-cause a production failure without
            # first having to reproduce it.
            logger.error(
                "TTS synthesis FAILED: task_id=%s segment=%s requested_engine=%s language=%s "
                "voice=%s error_type=%s error=%s",
                task_id, segment_index, resolved_engine, language, voice,
                type(exc).__name__, exc,
                exc_info=True,
                extra=log_context,
            )
            raise TTSGenerationError(f"TTS synthesis failed: {exc}") from exc

        if not response.success or response.output_path is None:
            logger.error(
                "TTS synthesis FAILED (no exception raised, response.success=False): task_id=%s "
                "segment=%s requested_engine=%s language=%s voice=%s response_engine=%s error=%s",
                task_id, segment_index, resolved_engine, language, voice,
                response.engine, response.error,
                extra=log_context,
            )
            raise TTSGenerationError(f"TTS synthesis failed: {response.error or 'unknown error'}")

        if response.engine != resolved_engine:
            logger.info(
                "Fallback engaged: task_id=%s segment=%s requested_engine=%s served_by=%s",
                task_id, segment_index, resolved_engine, response.engine,
                extra=log_context,
            )

        return str(response.output_path)

    def _compute_segment_windows(self, segments: List[SubtitleSegment]) -> List[float]:
        """
        Computes each segment's maximum allowed clip duration (its
        "window") for timeline alignment: the time available before the
        next segment starts, minus a small configured breathing gap.
        The last segment has nothing after it to collide with, so it
        gets a generous multiple of its own nominal duration instead.
        """
        gap = self._settings.TIMELINE_MIN_GAP_SECONDS
        windows: List[float] = []
        for index, segment in enumerate(segments):
            if index + 1 < len(segments):
                window = segments[index + 1].start - segment.start - gap
            else:
                window = max(segment.end - segment.start, 1.0) * 2.0
            windows.append(max(window, 0.1))
        return windows

    async def synthesize_segments(
        self,
        segments: List[SubtitleSegment],
        voice: str,
        task_id: str,
        file_manager: FileManager,
        engine: Optional[str] = None,
        language: str = "en",
    ) -> List[Tuple[SubtitleSegment, str]]:
        """
        Synthesizes every segment's `translated_text` into its own audio
        clip (bounded-concurrency parallel, up to `TTS_PARALLEL_WORKERS`
        at a time), applies per-clip DSP and timeline alignment to each
        (both individually configurable; both no-ops at default
        settings), and stores the resulting path on the segment itself.

        Fail-fast: if any segment fails, still-in-flight segments are
        cancelled and the whole call raises -- the same effective
        outcome as the prior strictly-sequential implementation, just
        reached without waiting for already-doomed sequential work.

        Args:
            segments: Segments with `translated_text` already populated.
            voice: The voice name/ID to use for all segments (engine-specific).
            task_id: The owning task's ID (used to namespace clip files and for logging).
            file_manager: Used to resolve per-segment output paths.
            engine: Registered engine name. Defaults to `DEFAULT_TTS_ENGINE`
                (gTTS), reproducing the platform's configured default
                behavior when omitted.
            language: ISO language code of the (translated) text being
                synthesized.

        Returns:
            A list of (segment, audio_clip_path) tuples, in segment order.

        Raises:
            TTSGenerationError: If any segment fails to synthesize.
        """
        resolved_engine = engine or self._settings.DEFAULT_TTS_ENGINE
        extension = _ENGINE_OUTPUT_EXTENSIONS.get(resolved_engine, _DEFAULT_OUTPUT_EXTENSION)

        speakable_segments = [s for s in segments if (s.translated_text or "").strip()]
        skipped_count = len(segments) - len(speakable_segments)
        if skipped_count:
            logger.warning(
                "Skipping %d segment(s) with no translated text for task %s.", skipped_count, task_id
            )

        if not speakable_segments:
            raise TTSGenerationError("No segments were successfully synthesized.")

        windows = self._compute_segment_windows(speakable_segments)
        semaphore = asyncio.Semaphore(max(1, self._settings.TTS_PARALLEL_WORKERS))
        ordered_results: List[Optional[Tuple[SubtitleSegment, str]]] = [None] * len(speakable_segments)

        async def _synthesize_one(position: int, segment: SubtitleSegment) -> None:
            async with semaphore:
                output_path = str(
                    file_manager.get_segment_audio_path(task_id, segment.index, extension=extension)
                )
                clip_path = await self.synthesize_segment(
                    text=segment.translated_text.strip(),
                    voice=voice,
                    output_path=output_path,
                    language=language,
                    engine=engine,
                    task_id=task_id,
                    segment_index=segment.index,
                )
                clip_path = await self._audio_processor.process_segment_clip(clip_path)
                fit = await self._audio_processor.fit_clip_to_window(clip_path, windows[position])
                clip_path = fit.path

                segment.tts_audio_path = clip_path
                ordered_results[position] = (segment, clip_path)

        tasks = [
            asyncio.create_task(_synthesize_one(position, segment))
            for position, segment in enumerate(speakable_segments)
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

        first_exception: Optional[BaseException] = None
        for finished_task in done:
            task_exc = finished_task.exception()
            if task_exc is not None and first_exception is None:
                first_exception = task_exc

        if first_exception is not None:
            for pending_task in pending:
                pending_task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            logger.error(
                "TTS segment synthesis aborted for task %s after a segment failure: %s",
                task_id, first_exception, exc_info=first_exception,
            )
            if isinstance(first_exception, TTSGenerationError):
                raise first_exception
            raise TTSGenerationError(f"TTS synthesis failed: {first_exception}") from first_exception

        results = [entry for entry in ordered_results if entry is not None]

        logger.info(
            "Synthesized %s TTS segment clip(s) for task %s using engine '%s' (parallel_workers=%s).",
            len(results), task_id, resolved_engine, self._settings.TTS_PARALLEL_WORKERS,
        )
        return results

    # ------------------------------------------------------------------
    # Timed Track Assembly (core mixing logic engine-agnostic and
    # unchanged from V3.0; Sprint 2 adds an optional final-track DSP pass)
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
        so the dub roughly tracks the source video's timing, then
        applies any enabled final-track DSP stages (equalizer, dynamic
        compression, peak limiter -- all disabled by default).

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
            "-c:a", self._settings.OUTPUT_AUDIO_CODEC,
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

        final_path = await self._audio_processor.process_final_track(output_path)

        logger.info("Dubbed audio track assembly complete: %s", final_path)
        return final_path

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

`build_dubbed_audio_track` (the FFmpeg-based timed-track assembly
step) is engine-agnostic and unchanged from the platform's original
implementation: it only cares about a list of (segment, clip_path)
pairs and never about which engine produced each clip.

This module's public surface -- `synthesize_segment`,
`synthesize_segments`, `build_dubbed_audio_track` -- stays backward
compatible: every new parameter is optional, so `services/pipeline.py`
needed only two additional keyword arguments at its existing call
site. Omitting `engine` resolves to whatever `DEFAULT_TTS_ENGINE` is
currently configured (gTTS by default), rather than any one engine
being hardcoded here.

Python: 3.12
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from config import Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from core.utils import run_command, seconds_to_ms
from models.task import SubtitleSegment
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
    """Text-to-speech synthesis (multi-engine) and timed audio track assembly."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._manager = TTSEngineManager(app_settings=app_settings)

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

        Returns:
            The `output_path` on success.

        Raises:
            TTSGenerationError: If synthesis fails on both the requested
                engine and the configured fallback engine.
        """
        metadata = {}
        if rate is not None:
            metadata["rate"] = rate
        if volume is not None:
            metadata["volume"] = volume
        if pitch is not None:
            metadata["pitch"] = pitch

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
            raise TTSGenerationError(f"TTS synthesis failed: {exc}") from exc

        if not response.success or response.output_path is None:
            raise TTSGenerationError(f"TTS synthesis failed: {response.error or 'unknown error'}")

        return str(response.output_path)

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
        clip, storing the resulting path on the segment itself.

        Args:
            segments: Segments with `translated_text` already populated.
            voice: The voice name/ID to use for all segments (engine-specific).
            task_id: The owning task's ID (used to namespace clip files).
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

        results: List[Tuple[SubtitleSegment, str]] = []

        for segment in segments:
            text = (segment.translated_text or "").strip()
            if not text:
                logger.warning("Segment %s has no translated text; skipping TTS.", segment.index)
                continue

            output_path = str(
                file_manager.get_segment_audio_path(task_id, segment.index, extension=extension)
            )
            await self.synthesize_segment(
                text=text, voice=voice, output_path=output_path, language=language, engine=engine
            )

            segment.tts_audio_path = output_path
            results.append((segment, output_path))

        if not results:
            raise TTSGenerationError("No segments were successfully synthesized.")

        logger.info(
            "Synthesized %s TTS segment clip(s) for task %s using engine '%s'.",
            len(results), task_id, resolved_engine,
        )
        return results

    # ------------------------------------------------------------------
    # Timed Track Assembly (engine-agnostic; unchanged from V3.0)
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

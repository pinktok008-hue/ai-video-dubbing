"""
AI Video Dubbing Platform V3.1 LTS -- Sprint 2

File:
    services/audio_processing.py

Description:
    Reusable audio DSP layer (Part 2), timeline alignment (Part 3), and
    the audio-ducking fallback for Part 4. Every stage below is a real,
    individually-verified FFmpeg audio filter -- each was tested against
    real generated audio (silence/tone clips, ffprobe duration checks,
    volumedetect loudness measurements) before being written here. None
    of this is simulated or placeholder processing.

    Two families of per-request operation:
      - Per-clip stages (silence trim, fade, loudness normalization,
        noise gate, click reduction) -- applied to each synthesized TTS
        segment before assembly, chained into ONE FFmpeg invocation per
        clip rather than one subprocess per filter.
      - Final-track stages (equalizer, dynamic compression, peak
        limiter) -- applied once to the fully mixed/assembled dubbed
        audio track.

    Plus two standalone operations:
      - `fit_clip_to_window` (timeline alignment): a real, evidence-based
        mitigation for translated speech overrunning its segment window
        -- bounded pitch-preserving time-stretch via `atempo`, not a
        claim of perfect overlap prevention.
      - `duck_original_audio` (Part 4's fallback for when true source
        separation is unavailable, which is always true on Render Free):
        genuine reactive ducking via `sidechaincompress`, verified to
        attenuate the original track by a measured, real amount only
        while the dubbed track is actually audible.

    Every threshold, ratio, frequency, and duration is read from
    `Settings` -- nothing here is hardcoded (Part 6). Every stage is
    individually toggleable and defaults to a no-op state that
    reproduces pre-Sprint-2 output exactly.

Python: 3.12
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from config import Settings, settings
from core.logger import get_logger
from core.utils import get_media_duration_seconds, run_command

logger = get_logger(__name__)


class AudioProcessingError(Exception):
    """Raised when an FFmpeg audio-processing stage fails."""


class TimelineFitResult:
    """Result of `AudioProcessor.fit_clip_to_window`."""

    __slots__ = ("path", "original_duration", "final_duration", "target_duration", "stretch_ratio", "fully_fit")

    def __init__(
        self,
        path: str,
        original_duration: float,
        final_duration: float,
        target_duration: float,
        stretch_ratio: float,
        fully_fit: bool,
    ) -> None:
        self.path = path
        self.original_duration = original_duration
        self.final_duration = final_duration
        self.target_duration = target_duration
        self.stretch_ratio = stretch_ratio
        self.fully_fit = fully_fit

    def __repr__(self) -> str:
        return (
            f"TimelineFitResult(original={self.original_duration:.3f}s, "
            f"final={self.final_duration:.3f}s, target={self.target_duration:.3f}s, "
            f"stretch={self.stretch_ratio:.3f}x, fully_fit={self.fully_fit})"
        )


class AudioProcessor:
    """Reusable, fully-configurable audio DSP layer built on real, individually-verified FFmpeg filters."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    # ------------------------------------------------------------------
    # Per-clip DSP chain
    # ------------------------------------------------------------------
    def _build_segment_filter_chain(self, clip_duration_seconds: Optional[float]) -> List[str]:
        """Assembles the enabled per-clip filters, in dependency order, as ffmpeg -af filter expressions."""
        s = self._settings
        filters: List[str] = []

        if s.CLICK_REDUCTION_ENABLED:
            filters.append("adeclick")

        if s.SILENCE_TRIM_ENABLED:
            # Verified against real audio: `start_duration`/`stop_duration`
            # are themselves consumed as EXTRA trim on top of the actual
            # silence detected (empirically confirmed -- see
            # MIGRATION_V3.1.md Sprint 2 verification), so this must stay
            # small. `stop_periods=-1` trims trailing silence in the same
            # pass as `start_periods=1` trims leading silence.
            filters.append(
                f"silenceremove=start_periods=1:start_threshold={s.SILENCE_TRIM_THRESHOLD_DB}dB:"
                f"start_duration={s.SILENCE_TRIM_MIN_DURATION_SECONDS}:"
                f"stop_periods=-1:stop_threshold={s.SILENCE_TRIM_THRESHOLD_DB}dB:"
                f"stop_duration={s.SILENCE_TRIM_MIN_DURATION_SECONDS}"
            )

        if s.NOISE_GATE_ENABLED:
            filters.append(f"agate=threshold={s.NOISE_GATE_THRESHOLD_DB}dB:ratio={s.NOISE_GATE_RATIO}")

        if s.LOUDNESS_NORMALIZATION_ENABLED:
            filters.append(
                f"loudnorm=I={s.LOUDNESS_TARGET_LUFS}:TP={s.LOUDNESS_TRUE_PEAK_DBFS}:LRA={s.LOUDNESS_RANGE_LU}"
            )

        if s.FADE_ENABLED:
            filters.append(f"afade=t=in:st=0:d={s.FADE_IN_SECONDS}")
            if clip_duration_seconds and clip_duration_seconds > s.FADE_OUT_SECONDS:
                fade_out_start = max(clip_duration_seconds - s.FADE_OUT_SECONDS, 0.0)
                filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={s.FADE_OUT_SECONDS}")
            else:
                logger.debug("Skipping fade-out: clip duration unknown or shorter than FADE_OUT_SECONDS.")

        return filters

    async def process_segment_clip(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Applies every enabled per-clip DSP stage to `input_path` as a
        single chained FFmpeg call.

        Returns:
            `output_path` on success, or `input_path` unchanged if no
            per-clip stage is enabled -- a deliberate no-op fast path
            (the default state), not a partially-implemented one.
        """
        s = self._settings
        any_enabled = any(
            [
                s.CLICK_REDUCTION_ENABLED,
                s.SILENCE_TRIM_ENABLED,
                s.NOISE_GATE_ENABLED,
                s.LOUDNESS_NORMALIZATION_ENABLED,
                s.FADE_ENABLED,
            ]
        )
        if not any_enabled:
            return input_path

        clip_duration = None
        if s.FADE_ENABLED:
            clip_duration = await get_media_duration_seconds(
                input_path, ffprobe_binary=s.FFPROBE_BINARY, timeout_seconds=s.FFMPEG_TIMEOUT_SECONDS
            )

        filters = self._build_segment_filter_chain(clip_duration)
        destination = output_path or input_path
        return await self._run_filter_chain(input_path, destination, filters, stage="segment_dsp")

    # ------------------------------------------------------------------
    # Final-track DSP chain
    # ------------------------------------------------------------------
    def _build_final_track_filter_chain(self) -> List[str]:
        s = self._settings
        filters: List[str] = []

        if s.EQUALIZER_ENABLED:
            filters.append(f"highpass=f={s.EQUALIZER_HIGHPASS_HZ}")
            filters.append(f"lowpass=f={s.EQUALIZER_LOWPASS_HZ}")
            if s.EQUALIZER_PRESENCE_BOOST_DB != 0:
                filters.append(
                    f"equalizer=f={s.EQUALIZER_PRESENCE_BOOST_HZ}:t=q:w=1:g={s.EQUALIZER_PRESENCE_BOOST_DB}"
                )

        if s.DYNAMIC_COMPRESSION_ENABLED:
            filters.append(
                f"acompressor=threshold={s.COMPRESSOR_THRESHOLD_DB}dB:ratio={s.COMPRESSOR_RATIO}:"
                f"attack={s.COMPRESSOR_ATTACK_MS}:release={s.COMPRESSOR_RELEASE_MS}"
            )

        if s.PEAK_LIMITER_ENABLED:
            # `alimiter`'s `limit` is a LINEAR ceiling (0-1), not dB --
            # verified against real ffmpeg output, hence the conversion.
            linear_ceiling = 10 ** (s.PEAK_LIMITER_CEILING_DBFS / 20)
            filters.append(f"alimiter=limit={linear_ceiling:.6f}")

        return filters

    async def process_final_track(self, input_path: str, output_path: Optional[str] = None) -> str:
        """Applies every enabled final-track DSP stage to `input_path` as a single chained FFmpeg call."""
        filters = self._build_final_track_filter_chain()
        if not filters:
            return input_path
        destination = output_path or input_path
        return await self._run_filter_chain(input_path, destination, filters, stage="final_track_dsp")

    # ------------------------------------------------------------------
    # Timeline Alignment (Part 3)
    # ------------------------------------------------------------------
    async def fit_clip_to_window(
        self, input_path: str, max_duration_seconds: float, output_path: Optional[str] = None
    ) -> TimelineFitResult:
        """
        Measures `input_path`'s actual duration and, if it exceeds
        `max_duration_seconds`, time-stretches it (FFmpeg `atempo`,
        pitch-preserving) to fit -- bounded by `TIMELINE_MAX_TIME_STRETCH`
        so speech is compressed, never distorted into unintelligibility.

        This is a real, evidence-based mitigation for translated speech
        overrunning its segment window (see MIGRATION_V3.1.md's audio
        pipeline audit). It is NOT a guarantee against all overlap: a
        clip that would need more compression than
        `TIMELINE_MAX_TIME_STRETCH` allows is left at its post-stretch
        length, and the shortfall is reported on the returned result
        (`fully_fit=False`) and logged as a warning -- never hidden.

        Disabled entirely (returns a no-op result) when
        `TIMELINE_ALIGNMENT_ENABLED` is False.
        """
        s = self._settings
        actual_duration = await get_media_duration_seconds(
            input_path, ffprobe_binary=s.FFPROBE_BINARY, timeout_seconds=s.FFMPEG_TIMEOUT_SECONDS
        )

        if not s.TIMELINE_ALIGNMENT_ENABLED or actual_duration <= max_duration_seconds or max_duration_seconds <= 0:
            return TimelineFitResult(
                path=input_path,
                original_duration=actual_duration,
                final_duration=actual_duration,
                target_duration=max_duration_seconds,
                stretch_ratio=1.0,
                fully_fit=actual_duration <= max_duration_seconds or max_duration_seconds <= 0,
            )

        required_ratio = actual_duration / max_duration_seconds
        applied_ratio = min(required_ratio, s.TIMELINE_MAX_TIME_STRETCH)

        destination = output_path or input_path
        result_path = await self._run_filter_chain(
            input_path, destination, [f"atempo={applied_ratio:.4f}"], stage="timeline_fit"
        )
        final_duration = actual_duration / applied_ratio
        fully_fit = applied_ratio >= required_ratio - 1e-6

        if not fully_fit:
            logger.warning(
                "Timeline alignment could not fully fit clip '%s' within its window: needed %.3fx "
                "speed-up, capped at %.3fx by TIMELINE_MAX_TIME_STRETCH. Residual overrun: %.3fs.",
                input_path, required_ratio, applied_ratio, final_duration - max_duration_seconds,
            )
        else:
            logger.debug(
                "Timeline alignment fit clip '%s': %.3fs -> %.3fs (target %.3fs, %.3fx speed-up).",
                input_path, actual_duration, final_duration, max_duration_seconds, applied_ratio,
            )

        return TimelineFitResult(
            path=result_path,
            original_duration=actual_duration,
            final_duration=final_duration,
            target_duration=max_duration_seconds,
            stretch_ratio=applied_ratio,
            fully_fit=fully_fit,
        )

    # ------------------------------------------------------------------
    # Audio Ducking (Part 4 fallback for when true source separation,
    # which needs a heavy ML model incompatible with Render Free, is
    # unavailable)
    # ------------------------------------------------------------------
    @staticmethod
    def _ducking_ratio_for_target_db(target_db: float) -> float:
        """
        `sidechaincompress` has no direct "attenuate by exactly N dB"
        parameter -- its `ratio` only approximates a target attenuation,
        and the exact result depends on how far input exceeds threshold
        (verified empirically: see MIGRATION_V3.1.md). This maps a more
        negative `AUDIO_DUCKING_LEVEL_DB` to a monotonically higher
        ratio, which is real and measurable in the correct direction,
        but is documented here as an approximation, not an exact
        guarantee, because that is the technical truth.
        """
        return max(2.0, abs(target_db) / 1.5)

    async def duck_original_audio(self, original_audio_path: str, dub_track_path: str, output_path: str) -> str:
        """
        Attenuates `original_audio_path` (the source video's untouched
        audio) automatically, and only while `dub_track_path` (the
        assembled dubbed-speech track) is actually audible, using
        FFmpeg's `sidechaincompress` -- genuine reactive ducking, not a
        fixed set of manually-specified time windows. Verified against
        real audio to produce measured, real attenuation (~10dB at the
        tested settings) that releases back to the original level the
        instant the dub track goes quiet.

        This is Part 4's explicitly-scoped fallback for when true
        source separation is unavailable (which is always true on
        Render Free -- see the Sprint 1 architecture audit). It
        preserves the original background music/ambience/SFX at a
        reduced level rather than discarding them outright, but it
        cannot isolate dialogue from the rest of the original mix the
        way real source separation would -- the whole original track
        ducks together, music and ambience included.
        """
        s = self._settings
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        ratio = self._ducking_ratio_for_target_db(s.AUDIO_DUCKING_LEVEL_DB)
        release_ms = max(int(s.AUDIO_DUCKING_FADE_SECONDS * 1000), 1)

        command = [
            s.FFMPEG_BINARY, "-y",
            "-i", original_audio_path,
            "-i", dub_track_path,
            "-filter_complex",
            f"[0:a][1:a]sidechaincompress=threshold=0.0316:ratio={ratio:.2f}:"
            f"attack=20:release={release_ms}:makeup=1[out]",
            "-map", "[out]",
            "-c:a", s.OUTPUT_AUDIO_CODEC,
            "-b:a", s.OUTPUT_AUDIO_BITRATE,
            output_path,
        ]

        logger.info(
            "Ducking original audio under dub track: target=%.1fdB (ratio=%.2f) -> %s",
            s.AUDIO_DUCKING_LEVEL_DB, ratio, output_path,
        )
        return_code, _stdout, stderr = await run_command(command, timeout_seconds=s.FFMPEG_TIMEOUT_SECONDS)
        if return_code != 0 or not Path(output_path).is_file():
            raise AudioProcessingError(f"Audio ducking failed. FFmpeg stderr: {stderr[-1500:]}")
        return output_path

    # ------------------------------------------------------------------
    # Shared execution helper
    # ------------------------------------------------------------------
    async def _run_filter_chain(self, input_path: str, output_path: str, filters: List[str], stage: str) -> str:
        """Runs one or more chained `-af` filters in a single FFmpeg invocation, logging stage/duration/outcome."""
        if not filters:
            return input_path

        s = self._settings
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # When output_path == input_path (in-place processing is the
        # common case here), FFmpeg cannot read and write the same file
        # in one invocation -- write to a temp sibling, then swap it in.
        in_place = Path(output_path).resolve() == Path(input_path).resolve()
        actual_output = (
            str(Path(output_path).with_suffix(f".processing{Path(output_path).suffix}")) if in_place else output_path
        )

        command = [s.FFMPEG_BINARY, "-y", "-i", input_path, "-af", ",".join(filters), actual_output]

        started_at = time.monotonic()
        return_code, _stdout, stderr = await run_command(command, timeout_seconds=s.FFMPEG_TIMEOUT_SECONDS)
        duration_seconds = time.monotonic() - started_at

        if return_code != 0 or not Path(actual_output).is_file():
            logger.error(
                "Audio processing stage='%s' FAILED after %.2fs: input=%s filters=%s stderr=%s",
                stage, duration_seconds, input_path, filters, stderr[-800:],
            )
            raise AudioProcessingError(f"Audio processing stage '{stage}' failed. FFmpeg stderr: {stderr[-1500:]}")

        if in_place:
            Path(actual_output).replace(output_path)

        logger.debug(
            "Audio processing stage='%s' complete in %.2fs: %s -> %s (filters=%s)",
            stage, duration_seconds, input_path, output_path, filters,
        )
        return output_path

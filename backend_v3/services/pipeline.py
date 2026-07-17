"""
services/pipeline.py
========================
Orchestrates the complete dubbing pipeline for a single task, from audio
extraction through final video render, delegating each step to its
dedicated service and reporting progress via `ProgressManager` along the
way. This is the only module that knows the overall stage ordering --
every service it calls is a single-responsibility unit that knows
nothing about the others.

Pipeline order:
    Extract Audio -> Transcribe -> Translate -> Generate Subtitles ->
    Synthesize Speech -> Remove Original Audio -> Merge Audio -> Done

Sprint 2 (Part 5): every stage above checks whether its expected output
already exists (and is durably recorded on the task, via TaskManager's
JSON persistence) before doing any work, and skips straight to the
next incomplete stage if so. Re-invoking `run()` for a task that
previously failed partway through resumes rather than restarts --
see core/task_manager.py for the durability/platform caveats.

Python: 3.12
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import PipelineStage, Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from core.progress_manager import ProgressManager
from core.task_manager import TaskManager
from models.task import DubbingTask, TaskStatus
from services.audio_cleaner import AudioCleaner
from services.audio_extractor import AudioExtractor
from services.audio_processing import AudioProcessor
from services.subtitle_service import SubtitleService
from services.transcription_service import TranscriptionService
from services.translation_service import TranslationService
from services.tts_service import TTSService
from services.video_merger import VideoMerger

logger = get_logger(__name__)


class PipelineExecutionError(Exception):
    """Raised when the pipeline cannot continue after all internal retries."""


class DubbingPipeline:
    """
    Coordinates every service required to turn an uploaded video into a
    fully dubbed output video, updating task progress at each stage.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        progress_manager: ProgressManager,
        file_manager: FileManager,
        audio_extractor: AudioExtractor,
        transcription_service: TranscriptionService,
        translation_service: TranslationService,
        subtitle_service: SubtitleService,
        tts_service: TTSService,
        audio_cleaner: AudioCleaner,
        video_merger: VideoMerger,
        app_settings: Settings = settings,
        audio_processor: Optional[AudioProcessor] = None,
    ) -> None:
        self._task_manager = task_manager
        self._progress_manager = progress_manager
        self._file_manager = file_manager
        self._audio_extractor = audio_extractor
        self._transcription_service = transcription_service
        self._translation_service = translation_service
        self._subtitle_service = subtitle_service
        self._tts_service = tts_service
        self._audio_cleaner = audio_cleaner
        self._video_merger = video_merger
        self._settings = app_settings
        self._audio_processor = audio_processor or AudioProcessor(app_settings=app_settings)

    async def run(self, task_id: str, burn_subtitles: bool = False) -> None:
        """
        Executes the full dubbing pipeline for the given task. Any
        exception raised by an underlying service is caught, logged, and
        recorded on the task as a FAILED status with an error message --
        this method never raises back to its caller (the background
        task runner in app.py) so a single failed job never crashes the
        server process.

        Args:
            task_id: The task to process.
            burn_subtitles: If True, embed the translated subtitles as a
                soft subtitle stream in the final output video.
        """
        try:
            task = await self._task_manager.require_task(task_id)
            await self._run_pipeline(task, burn_subtitles=burn_subtitles)
        except Exception as exc:  # noqa: BLE001 - a failed task must never crash the server.
            logger.error("Pipeline failed for task %s: %s", task_id, exc, exc_info=True)
            await self._fail_task(task_id, str(exc))

    @staticmethod
    def _existing_file(path: Optional[str]) -> Optional[str]:
        """Returns `path` if it is set and the file actually exists on disk, else None."""
        if path and Path(path).is_file():
            return path
        return None

    async def _run_pipeline(self, task: DubbingTask, burn_subtitles: bool) -> None:
        task_id = task.task_id

        # ---- Stage: Audio Extraction ------------------------------------
        await self._progress_manager.update(task_id, PipelineStage.AUDIO_EXTRACTION)
        extracted_audio_path = self._existing_file(task.extracted_audio_path)
        if extracted_audio_path:
            logger.info("Resuming task %s: audio extraction already complete, skipping.", task_id)
        else:
            extracted_audio_path = str(self._file_manager.get_extracted_audio_path(task_id))
            await self._audio_extractor.extract(task.video_path, extracted_audio_path)
            task.extracted_audio_path = extracted_audio_path
            await self._task_manager.update_task(task)

        # ---- Stage: Transcription (Groq Whisper) -------------------------
        await self._progress_manager.update(task_id, PipelineStage.TRANSCRIPTION)
        if task.segments and any((segment.text or "").strip() for segment in task.segments):
            logger.info("Resuming task %s: transcription already complete, skipping.", task_id)
        else:
            detected_language, segments = await self._transcription_service.transcribe(
                audio_path=extracted_audio_path,
                source_language=task.source_language,
            )
            task.detected_language = detected_language
            task.segments = segments
            if not task.source_language:
                task.source_language = detected_language
            await self._task_manager.update_task(task)

        # ---- Stage: Translation -------------------------------------------
        await self._progress_manager.update(task_id, PipelineStage.TRANSLATION)
        target_language = task.target_language or task.source_language
        if task.segments and all((segment.translated_text or "").strip() for segment in task.segments):
            logger.info("Resuming task %s: translation already complete, skipping.", task_id)
        else:
            translated_segments = await self._translation_service.translate_segments(
                segments=task.segments,
                source_language=task.source_language,
                target_language=target_language,
            )
            task.segments = translated_segments
            await self._task_manager.update_task(task)

        # ---- Stage: Subtitle Generation -----------------------------------
        await self._progress_manager.update(task_id, PipelineStage.SUBTITLE_GENERATION)
        original_subtitle_path = self._existing_file(task.subtitle_path_original)
        translated_subtitle_path = self._existing_file(task.subtitle_path_translated)
        if original_subtitle_path and translated_subtitle_path:
            logger.info("Resuming task %s: subtitles already generated, skipping.", task_id)
        else:
            original_subtitle_path = str(self._file_manager.get_subtitle_path(task_id, translated=False))
            translated_subtitle_path = str(self._file_manager.get_subtitle_path(task_id, translated=True))
            self._subtitle_service.generate_srt(task.segments, original_subtitle_path, use_translated_text=False)
            self._subtitle_service.generate_srt(task.segments, translated_subtitle_path, use_translated_text=True)
            task.subtitle_path_original = original_subtitle_path
            task.subtitle_path_translated = translated_subtitle_path
            await self._task_manager.update_task(task)

        # ---- Stage: TTS Generation ------------------------------------------
        await self._progress_manager.update(task_id, PipelineStage.TTS_GENERATION)
        voice = task.voice or Settings.get_default_voice(target_language)
        task.voice = voice
        final_audio_path = self._existing_file(task.dubbed_audio_path)
        if final_audio_path:
            logger.info("Resuming task %s: TTS + audio assembly already complete, skipping.", task_id)
        else:
            segments_with_audio = await self._tts_service.synthesize_segments(
                segments=task.segments,
                voice=voice,
                task_id=task_id,
                file_manager=self._file_manager,
                engine=task.tts_engine,
                language=target_language,
            )
            video_duration = await self._video_merger.get_duration_seconds(task.video_path)
            dubbed_audio_path = str(self._file_manager.get_dubbed_audio_path(task_id))
            dubbed_audio_path = await self._tts_service.build_dubbed_audio_track(
                segments_with_audio=segments_with_audio,
                total_duration_seconds=video_duration,
                output_path=dubbed_audio_path,
            )

            # Part 4 (Sprint 2): when true source separation is unavailable
            # (always true on Render Free -- see the Sprint 1 architecture
            # audit), the best available production fallback is to duck the
            # ORIGINAL audio under the dubbed speech rather than discard it
            # outright, preserving background music/ambience/SFX at a
            # reduced level. Opt-in (AUDIO_DUCKING_ENABLED defaults False)
            # since it changes the final mix -- never silently applied.
            final_audio_path = dubbed_audio_path
            if self._settings.AUDIO_DUCKING_ENABLED and task.extracted_audio_path:
                dub_path_obj = Path(dubbed_audio_path)
                ducked_audio_path = str(
                    dub_path_obj.with_name(f"{dub_path_obj.stem}_ducked{dub_path_obj.suffix}")
                )
                final_audio_path = await self._audio_processor.duck_original_audio(
                    original_audio_path=task.extracted_audio_path,
                    dub_track_path=dubbed_audio_path,
                    output_path=ducked_audio_path,
                )

            task.dubbed_audio_path = final_audio_path
            await self._task_manager.update_task(task)

        # ---- Stage: Remove Original Audio ------------------------------------
        await self._progress_manager.update(task_id, PipelineStage.AUDIO_CLEANUP)
        silent_video_path = self._existing_file(task.silent_video_path)
        if silent_video_path:
            logger.info("Resuming task %s: original audio already stripped, skipping.", task_id)
        else:
            silent_video_path = str(self._file_manager.get_silent_video_path(task_id))
            await self._audio_cleaner.strip_audio(task.video_path, silent_video_path)
            task.silent_video_path = silent_video_path
            await self._task_manager.update_task(task)

        # ---- Stage: Merge Audio (Final Render) --------------------------------
        await self._progress_manager.update(task_id, PipelineStage.AUDIO_MERGE)
        output_video_path = self._existing_file(task.output_video_path)
        if output_video_path:
            logger.info("Resuming task %s: final render already complete, skipping.", task_id)
        else:
            output_video_path = str(self._file_manager.get_output_video_path(task_id))
            subtitle_to_embed = translated_subtitle_path if burn_subtitles else None
            await self._video_merger.merge(
                silent_video_path=silent_video_path,
                dubbed_audio_path=final_audio_path,
                output_video_path=output_video_path,
                subtitle_path=subtitle_to_embed,
            )
            task.output_video_path = output_video_path
            await self._task_manager.update_task(task)

        # ---- Stage: Finalizing / Completed --------------------------------------
        await self._progress_manager.update(task_id, PipelineStage.FINALIZING)
        task.mark_completed()
        await self._task_manager.update_task(task)
        await self._progress_manager.update(
            task_id, PipelineStage.COMPLETED, status_override=TaskStatus.COMPLETED
        )

    async def _fail_task(self, task_id: str, error_message: str) -> None:
        """Marks a task as failed, tolerating the task having disappeared mid-run."""
        try:
            task = await self._task_manager.require_task(task_id)
            task.mark_failed(error_message)
            await self._task_manager.update_task(task)
        except KeyError:
            logger.warning("Could not mark task %s as failed: task no longer exists.", task_id)

"""
AI Video Dubbing Pipeline
Version 2.1

This module orchestrates the complete dubbing workflow.
"""

from core.logger import task_log, task_error
from core.progress_manager import progress_manager

from services.audio_extractor import extract_audio
from services.transcription_service import transcribe_audio
from services.translation_service import translate_text
from services.tts_service import generate_speech
from services.video_merger import merge_video_audio
from services.audio_cleaner import remove_original_audio


class DubbingPipeline:

    def process(
        self,
        task_id: str,
        video_path: str,
        audio_path: str,
        clean_video_path: str,
        speech_path: str,
        output_path: str,
        target_language: str
    ):

        try:

            task_log(task_id, "Pipeline", "Started")

            # -----------------------------------
            # Extract Audio
            # -----------------------------------

            progress_manager.extracting_audio(task_id)

            extract_audio(
                video_path,
                audio_path,
                task_id
            )

            # -----------------------------------
            # Speech Recognition
            # -----------------------------------

            progress_manager.transcribing(task_id)

            transcription = transcribe_audio(
                audio_path,
                task_id
            )

            if transcription["status"] != "success":
                raise Exception(
                    transcription["message"]
                )

            # -----------------------------------
            # Translation
            # -----------------------------------

            progress_manager.translating(task_id)

            translation = translate_text(
                text=transcription["text"],
                target_language=target_language,
                source_language="auto",
                task_id=task_id
            )

            if translation["status"] != "success":
                raise Exception(
                    translation["message"]
                )

            # -----------------------------------
            # Speech Generation
            # -----------------------------------

            progress_manager.generating_audio(task_id)

            speech = generate_speech(
                text=translation["translated_text"],
                output_path=speech_path,
                task_id=task_id
            )

            if speech["status"] != "success":
                raise Exception(
                    speech["message"]
                )

            # -----------------------------------
            # Remove Original Audio
            # -----------------------------------

            progress_manager.update(
                task_id,
                82,
                "Audio Cleanup",
                "Removing original audio..."
            )

            remove_original_audio(
                video_path,
                clean_video_path
            )

            # -----------------------------------
            # Render
            # -----------------------------------

            progress_manager.rendering(task_id)

            merge_video_audio(
                video_path=clean_video_path,
                dubbed_audio_path=speech_path,
                output_path=output_path,
                task_id=task_id
            )

            progress_manager.completed(
                task_id,
                output_path
            )

            task_log(
                task_id,
                "Pipeline",
                "Completed"
            )

            return output_path

        except Exception as e:

            progress_manager.failed(
                task_id,
                str(e)
            )

            task_error(
                task_id,
                "Pipeline",
                str(e)
            )

            raise


pipeline = DubbingPipeline()

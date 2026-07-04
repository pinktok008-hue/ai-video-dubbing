"""
AI Video Dubbing Platform
Version : 2.0

Progress Manager
"""

from datetime import datetime
from core.task_manager import task_manager


class ProgressManager:

    def update(
        self,
        task_id: str,
        progress: int,
        stage: str,
        message: str
    ):

        task_manager.update_progress(
            task_id=task_id,
            progress=progress,
            stage=stage,
            message=message
        )

    # -----------------------------------

    def uploading(self, task_id):

        self.update(
            task_id,
            5,
            "Uploading",
            "Uploading video..."
        )

    # -----------------------------------

    def validating(self, task_id):

        self.update(
            task_id,
            10,
            "Validation",
            "Validating video..."
        )

    # -----------------------------------

    def extracting_audio(self, task_id):

        self.update(
            task_id,
            20,
            "Audio Extraction",
            "Extracting audio..."
        )

    # -----------------------------------

    def transcribing(self, task_id):

        self.update(
            task_id,
            35,
            "Speech Recognition",
            "Transcribing audio..."
        )

    # -----------------------------------

    def translating(self, task_id):

        self.update(
            task_id,
            50,
            "Translation",
            "Translating subtitles..."
        )

    # -----------------------------------

    def voice_clone(self, task_id):

        self.update(
            task_id,
            65,
            "Voice Clone",
            "Generating cloned voice..."
        )

    # -----------------------------------

    def generating_audio(self, task_id):

        self.update(
            task_id,
            75,
            "Speech Generation",
            "Generating dubbed speech..."
        )

    # -----------------------------------

    def lip_sync(self, task_id):

        self.update(
            task_id,
            85,
            "Lip Sync",
            "Synchronizing lips..."
        )

    # -----------------------------------

    def rendering(self, task_id):

        self.update(
            task_id,
            95,
            "Rendering",
            "Rendering final video..."
        )

    # -----------------------------------

    def completed(
        self,
        task_id,
        download_url
    ):

        task_manager.complete_task(
            task_id,
            download_url
        )

    # -----------------------------------

    def failed(
        self,
        task_id,
        error
    ):

        task_manager.fail_task(
            task_id,
            str(error)
        )

    # -----------------------------------

    def status(
        self,
        task_id
    ):

        return task_manager.get_task(task_id)


progress_manager = ProgressManager()

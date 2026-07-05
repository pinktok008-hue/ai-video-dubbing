"""
AI Video Dubbing Platform
Version 2.2

Speaker Detection Service
"""

from pathlib import Path
from typing import List, Dict

from core.logger import task_log, task_error


class SpeakerService:

    def __init__(self):

        self.pipeline = None

    def load(self):

        """
        Lazy loading of pyannote model.
        """

        if self.pipeline is not None:
            return

        try:

            from pyannote.audio import Pipeline
            import os

            token = os.getenv("HF_TOKEN")

            if not token:
                raise RuntimeError(
                    "HF_TOKEN not found."
                )

            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token
            )

        except Exception as e:
            raise RuntimeError(str(e))

    def detect(
        self,
        audio_path: str,
        task_id: str | None = None
    ) -> List[Dict]:

        if not Path(audio_path).exists():
            raise FileNotFoundError(audio_path)

        try:

            if task_id:

                task_log(
                    task_id,
                    "Speaker Detection",
                    "Started"
                )

            self.load()

            diarization = self.pipeline(audio_path)

            speakers = []

            for segment, _, speaker in diarization.itertracks(
                yield_label=True
            ):

                speakers.append({

                    "speaker": speaker,

                    "start": round(
                        segment.start,
                        2
                    ),

                    "end": round(
                        segment.end,
                        2
                    )

                })

            if task_id:

                task_log(
                    task_id,
                    "Speaker Detection",
                    "Completed"
                )

            return speakers

        except Exception as e:

            if task_id:

                task_error(
                    task_id,
                    "Speaker Detection",
                    str(e)
                )

            raise


speaker_service = SpeakerService()

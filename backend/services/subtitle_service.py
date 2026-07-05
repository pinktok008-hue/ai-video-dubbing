"""
AI Video Dubbing Platform
Version 2.3

Subtitle Generation Service
"""

from pathlib import Path
from typing import List, Dict

from core.logger import task_log, task_error


class SubtitleService:

    @staticmethod
    def _format_time(seconds: float) -> str:

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return (
            f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
        )

    def generate_srt(
        self,
        segments: List[Dict],
        output_path: str,
        task_id: str | None = None
    ) -> str:

        try:

            if task_id:
                task_log(
                    task_id,
                    "Subtitle",
                    "Generating SRT"
                )

            Path(output_path).parent.mkdir(
                parents=True,
                exist_ok=True
            )

            with open(
                output_path,
                "w",
                encoding="utf-8"
            ) as f:

                for index, segment in enumerate(
                    segments,
                    start=1
                ):

                    start = self._format_time(
                        segment["start"]
                    )

                    end = self._format_time(
                        segment["end"]
                    )

                    text = segment["text"].strip()

                    f.write(f"{index}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")

            if task_id:
                task_log(
                    task_id,
                    "Subtitle",
                    "Completed"
                )

            return output_path

        except Exception as e:

            if task_id:
                task_error(
                    task_id,
                    "Subtitle",
                    str(e)
                )

            raise


subtitle_service = SubtitleService()

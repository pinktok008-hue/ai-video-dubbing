"""
AI Video Dubbing Platform
Version 2.0

Speech Transcription Service
"""

import os

from groq import Groq

from core.logger import task_log, task_error


MODEL_NAME = "whisper-large-v3"


def transcribe_audio(
    audio_path: str,
    task_id: str | None = None
) -> dict:
    """
    Transcribe speech using Groq Whisper.

    Returns
    -------
    {
        "status": "success",
        "text": "...",
        "language": "unknown"
    }
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return {
            "status": "error",
            "message": "GROQ_API_KEY not found."
        }

    try:

        if task_id:
            task_log(
                task_id,
                "Speech Recognition",
                "Started"
            )

        client = Groq(api_key=api_key)

        with open(audio_path, "rb") as audio_file:

            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model=MODEL_NAME,
                response_format="verbose_json"
            )

        text = getattr(
            transcription,
            "text",
            ""
        )

        language = getattr(
            transcription,
            "language",
            "unknown"
        )

        if task_id:
            task_log(
                task_id,
                "Speech Recognition",
                "Completed"
            )

        return {
            "status": "success",
            "text": text,
            "language": language
        }

    except Exception as e:

        if task_id:
            task_error(
                task_id,
                "Speech Recognition",
                str(e)
            )

        return {
            "status": "error",
            "message": str(e)
        }

"""
AI Video Dubbing Platform
Version 2.0

Text To Speech Service
"""

import os
import asyncio
from pathlib import Path

import edge_tts

from core.logger import task_log, task_error


DEFAULT_VOICE = "en-US-AndrewNeural"


async def _generate(
    text: str,
    output_path: str,
    voice: str
):

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice
    )

    await communicate.save(output_path)


def generate_speech(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
    task_id: str | None = None
) -> dict:
    """
    Generate speech using Edge TTS.

    Returns
    -------
    {
        "status":"success",
        "audio_path":"..."
    }
    """

    try:

        if not text.strip():

            return {

                "status": "error",

                "message": "Empty text."

            }

        Path(
            os.path.dirname(output_path)
        ).mkdir(
            parents=True,
            exist_ok=True
        )

        if task_id:

            task_log(

                task_id,

                "Speech Generation",

                "Started"

            )

        asyncio.run(

            _generate(

                text,

                output_path,

                voice

            )

        )

        if task_id:

            task_log(

                task_id,

                "Speech Generation",

                "Completed"

            )

        return {

            "status": "success",

            "audio_path": output_path

        }

    except Exception as e:

        if task_id:

            task_error(

                task_id,

                "Speech Generation",

                str(e)

            )

        return {

            "status": "error",

            "message": str(e)

        }

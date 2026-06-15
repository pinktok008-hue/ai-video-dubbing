import os
from groq import Groq

def transcribe_audio(audio_path):
    try:
        client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3"
            )

        return {
            "status": "success",
            "text": transcription.text
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

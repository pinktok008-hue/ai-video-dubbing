import os
import asyncio
import edge_tts

async def generate_edge_tts(text, language):

    voices = {
        "Hindi": "hi-IN-SwaraNeural",
        "English": "en-US-JennyNeural",
        "German": "de-DE-KatjaNeural",
        "French": "fr-FR-DeniseNeural",
        "Spanish": "es-ES-ElviraNeural",
        "Chinese": "zh-CN-XiaoxiaoNeural",
        "Japanese": "ja-JP-NanamiNeural",
        "Korean": "ko-KR-SunHiNeural"
    }

    voice = voices.get(
        language,
        "en-US-JennyNeural"
    )

    output_file = "audio/generated_voice.mp3"

    communicate = edge_tts.Communicate(
        text,
        voice
    )

    await communicate.save(output_file)

    return output_file


def generate_speech(
    text,
    language="English"
):

    try:

        audio_file = asyncio.run(
            generate_edge_tts(
                text,
                language
            )
        )

        return {
            "status": "success",
            "audio_file": audio_file,
            "text": text
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

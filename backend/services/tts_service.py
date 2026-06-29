import edge_tts


async def generate_speech(
    text,
    language="English"
):

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

    return {
        "status": "success",
        "audio_file": output_file,
        "text": text
    }

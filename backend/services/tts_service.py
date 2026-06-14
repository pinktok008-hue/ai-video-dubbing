from gtts import gTTS
from pathlib import Path

LANGUAGE_CODES = {
    "English": "en",
    "Hindi": "hi",
    "Bengali": "bn",
    "German": "de",
    "Chinese": "zh-CN",
    "Korean": "ko"
}

def generate_speech(text, language="English"):

    Path("audio").mkdir(exist_ok=True)

    output_file = "audio/generated_voice.mp3"

    lang_code = LANGUAGE_CODES.get(
        language,
        "en"
    )

    tts = gTTS(
        text=text,
        lang=lang_code
    )

    tts.save(output_file)

    return {
        "status": "success",
        "audio_file": output_file,
        "language": language,
        "text": text
    }

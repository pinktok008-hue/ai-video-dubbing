from gtts import gTTS
from pathlib import Path

def generate_speech(text):

    Path("audio").mkdir(exist_ok=True)

    output_file = "audio/generated_voice.mp3"

    tts = gTTS(
        text=text,
        lang="en"
    )

    tts.save(output_file)

    return {
        "status": "success",
        "audio_file": output_file,
        "text": text
    }

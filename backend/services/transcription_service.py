import whisper

model = whisper.load_model("tiny")

def transcribe_audio(audio_path):

    result = model.transcribe(audio_path)

    return {
        "status": "success",
        "text": result["text"]
    }

from fastapi import FastAPI, UploadFile, File
import os
import subprocess
from services.audio_extractor import extract_audio
from services.transcription_service import transcribe_audio
from services.translation_service import translate_text
from services.tts_service import generate_speech

app = FastAPI()

UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "audio"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

@app.get("/")
def home():
    return {
        "message": "AI Video Dubbing API Running"
    }

@app.post("/upload")
async def upload_video(video: UploadFile = File(...)):
    file_path = os.path.join(
        UPLOAD_FOLDER,
        video.filename
    )

    with open(file_path, "wb") as f:
        f.write(await video.read())

    return {
        "status": "success",
        "filename": video.filename
    }

@app.get("/ffmpeg-test")
def ffmpeg_test():
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )

        return {
            "installed": True,
            "output": result.stdout[:300]
        }

    except Exception as e:
        return {
            "installed": False,
            "error": str(e)
        }

@app.post("/extract-audio")
async def extract_audio_api(video: UploadFile = File(...)):
    video_path = os.path.join(
        UPLOAD_FOLDER,
        video.filename
    )

    with open(video_path, "wb") as f:
        f.write(await video.read())

    audio_name = os.path.splitext(video.filename)[0] + ".wav"

    audio_path = os.path.join(
        AUDIO_FOLDER,
        audio_name
    )

    extract_audio(
        video_path,
        audio_path
    )

    return {
        "status": "success",
        "audio_file": audio_name
    }

@app.post("/transcribe")
async def transcribe_api():
    result = transcribe_audio("sample.wav")
    return result

@app.get("/translate")
def translate_api(
    text: str = "Hello world",
    language: str = "Hindi"
):
    result = translate_text(
        text,
        language
    )

    return result

@app.get("/tts")
def tts_api(
    text: str = "Hello world",
    language: str = "English"
):
    result = generate_speech(
        text,
        language
    )

    return result

from fastapi.responses import FileResponse

@app.get("/download-audio")
def download_audio():
    return FileResponse(
        "audio/generated_voice.mp3",
        media_type="audio/mpeg",
        filename="generated_voice.mp3"
    )

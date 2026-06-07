```python
from fastapi import FastAPI, UploadFile, File
import os
import subprocess
from services.audio_extractor import extract_audio

app = FastAPI()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("audio", exist_ok=True)

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
            "output": result.stdout[:500]
        }

    except Exception as e:
        return {
            "installed": False,
            "error": str(e)
        }

@app.post("/extract-audio")
async def extract_audio_api(
    video: UploadFile = File(...)
):
    video_path = os.path.join(
        UPLOAD_FOLDER,
        video.filename
    )

    with open(video_path, "wb") as f:
        f.write(await video.read())

    audio_name = (
        os.path.splitext(video.filename)[0]
        + ".wav"
    )

    audio_path = os.path.join(
        "audio",
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
```

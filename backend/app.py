from fastapi import FastAPI, UploadFile, File
import os
import subprocess

app = FastAPI()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.get("/")
def home():
    return {"message": "AI Video Dubbing API Running"}

@app.post("/upload")
async def upload_video(video: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_FOLDER, video.filename)

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

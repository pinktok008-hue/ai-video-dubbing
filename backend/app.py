from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import uuid
import traceback
import asyncio

from services.audio_extractor import extract_audio
from services.transcription_service import transcribe_audio
from services.translation_service import translate_text
from services.tts_service import generate_speech
from services.video_merger import merge_video_audio
from services.audio_cleaner import remove_original_audio


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "audio"
VIDEO_FOLDER = "video"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)


# Job Status Store
jobs = {}


@app.get("/")
def home():
    return {
        "message": "AI Video Dubbing API Running",
        "status": "online"
    }

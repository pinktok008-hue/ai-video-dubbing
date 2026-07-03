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


async def process_video(job_id, video_path, language):

    try:

        # Extract Audio
        jobs[job_id] = {
            "status": "Extracting audio...",
            "progress": 20
        }

        audio_name = os.path.splitext(
            os.path.basename(video_path)
        )[0] + ".wav"

        audio_path = os.path.join(
            AUDIO_FOLDER,
            audio_name
        )

        extract_audio(
            video_path,
            audio_path
        )



        # Transcription
        jobs[job_id] = {
            "status": "Transcribing...",
            "progress": 40
        }

        transcription = transcribe_audio(
            audio_path
        )



        # Translation
        jobs[job_id] = {
            "status": "Translating...",
            "progress": 60
        }

        translation = translate_text(
            transcription["text"],
            language
        )



        # AI Voice
        jobs[job_id] = {
            "status": "Generating AI Voice...",
            "progress": 80
        }

        speech = await generate_speech(
            translation["translated_text"],
            language
        )



        # Remove Original Audio
        clean_video = os.path.join(
            VIDEO_FOLDER,
            "clean_" + os.path.basename(video_path)
        )

        remove_original_audio(
            video_path,
            clean_video
        )



        # Merge
        output_video = os.path.join(
            VIDEO_FOLDER,
            "dubbed_" + os.path.basename(video_path)
        )

        merge_video_audio(
            clean_video,
            speech["audio_file"],
            output_video
        )



        jobs[job_id] = {
            "status": "Completed",
            "progress": 100,
            "video": output_video
        }


    except Exception as e:

        traceback.print_exc()

        jobs[job_id] = {
    "status": "Failed",
    "progress": 0,
    "message": str(e)
        }


@app.post("/dub-video")
async def dub_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    language: str = "Hindi"
):

    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "Uploading...",
        "progress": 10
    }

    video_path = os.path.join(
        UPLOAD_FOLDER,
        video.filename
    )

    with open(video_path, "wb") as f:
        f.write(await video.read())

    background_tasks.add_task(
        process_video,
        job_id,
        video_path,
        language
    )

    return {
        "status": "started",
        "job_id": job_id
    }


@app.get("/status/{job_id}")
def status(job_id: str):

    return jobs.get(
        job_id,
        {
            "error": "Job not found"
        }
    )


@app.get("/download-video/{job_id}")
def download_video(job_id: str):

    if job_id not in jobs:
        return {
            "error": "Job not found"
        }

    return FileResponse(
        jobs[job_id]["video"],
        media_type="video/mp4",
        filename="dubbed_video.mp4"
    )

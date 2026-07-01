from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse

import os
import subprocess
import uuid


from services.audio_extractor import extract_audio
from services.transcription_service import transcribe_audio
from services.translation_service import translate_text
from services.tts_service import generate_speech
from services.video_merger import merge_video_audio
from services.audio_cleaner import remove_original_audio



app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware


app.add_middleware(

CORSMiddleware,

allow_origins=["*"],

allow_methods=["*"],

allow_headers=["*"],

)


jobs = {}







UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "audio"
VIDEO_FOLDER = "video"



os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)





@app.get("/")
def home():

    return {
        "message": "AI Video Dubbing API Running"
    }





# Upload test

@app.post("/upload")
async def upload_video(
    video: UploadFile = File(...)
):

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






# FFmpeg check

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







# Extract audio

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








# Transcription test

@app.post("/transcribe")
async def transcribe_api():

    result = transcribe_audio(

        "sample.wav"

    )


    return result







# Translation test

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








# TTS test

@app.get("/tts")
async def tts_api(

    text: str = "Hello world",

    language: str = "English"

):


    result = await generate_speech(

        text,

        language

    )


    return result







# Download audio

@app.get("/download-audio")
def download_audio():


    return FileResponse(

        "audio/generated_voice.mp3",

        media_type="audio/mpeg",

        filename="generated_voice.mp3"

    )








# MAIN DUBBING API

@app.post("/dub-video")
async def dub_video(

    video: UploadFile = File(...),

    language: str = "Hindi"

):


    job_id = str(uuid.uuid4())



    jobs[job_id] = {

        "status": "started",

        "progress": 0

    }





    # Save video


    video_path = os.path.join(

        UPLOAD_FOLDER,

        video.filename

    )



    with open(video_path, "wb") as f:


        f.write(await video.read())




            jobs[job_id].update({
        "status": "VIDEO SAVED",
        "progress": 20
    })

    print("VIDEO SAVED", flush=True)



    # Extract audio


    audio_name = (

        os.path.splitext(video.filename)[0]

        + ".wav"

    )


    audio_path = os.path.join(

        AUDIO_FOLDER,

        audio_name

    )



    extract_audio(

        video_path,

        audio_path

    )







    # Transcribe


    transcription = transcribe_audio(

        audio_path

    )

    
    jobs[job_id].update({
    "status": "TRANSCRIPTION DONE",
    "progress": 50
})






    # Translate


    translation = translate_text(

        transcription["text"],

        language

    )



    jobs[job_id].update({
    "status": "TRANSLATION DONE",
    "progress": 65
})







    # Generate voice


    speech = await generate_speech(

        translation["translated_text"],

        language

    )



        jobs[job_id].update({
        "status":"TTS DONE",
        "progress":80
    })

    print("TTS DONE", flush=True)





    # Remove original audio


    clean_video = os.path.join(

        VIDEO_FOLDER,

        "clean_video.mp4"

    )



    remove_original_audio(

        video_path,

        clean_video

    )








    # Merge audio + video


    output_video = os.path.join(

        VIDEO_FOLDER,

        "dubbed_video.mp4"

    )

    



    merge_video_audio(

        clean_video,

        speech["audio_file"],

        output_video

    )





        jobs[job_id].update({
        "status":"MERGE DONE",
        "progress":100
    })

    print("MERGE DONE", flush=True)


    return {


        "status": "success",

        "job_id": job_id,

        "video_file": output_video,

        "audio_file": speech["audio_file"],

        "language": language

    }









# Download video


@app.get("/download-video")
def download_video():


    return FileResponse(

        "video/dubbed_video.mp4",

        media_type="video/mp4",

        filename="dubbed_video.mp4"

    )









# Progress status


@app.get("/status/{job_id}")

def status(job_id: str):


    return jobs.get(

        job_id,

        {

            "error": "job not found"

        }

    )

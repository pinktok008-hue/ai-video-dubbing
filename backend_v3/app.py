"""
app.py
=======
FastAPI application entrypoint for the AI Video Dubbing Platform V3.0.

Wires together every core component (logger, file manager, task manager,
progress manager) and every pipeline service (audio extraction,
transcription, translation, subtitles, TTS, audio cleanup, video merge)
via simple constructor-based dependency injection, and exposes the
public REST API:

    GET    /                   - Service info
    GET    /health             - Health check
    POST   /upload             - Upload a source video
    POST   /dub                - Start the dubbing pipeline for an uploaded video
    GET    /status/{task_id}   - Poll task progress
    GET    /download/{task_id} - Download the finished dubbed video
    DELETE /task/{task_id}     - Cancel/delete a task and its files
    GET    /languages          - List supported languages
    GET    /voices             - List available Edge TTS voices
    GET    /tts/engines        - List registered TTS engines, availability & capabilities

Python: 3.12
"""

from __future__ import annotations

import shutil
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import EDGE_TTS_ALL_VOICES, SUPPORTED_LANGUAGES, Settings, settings
from core.file_manager import FileManager
from core.logger import get_logger
from core.progress_manager import ProgressManager
from core.task_manager import TaskManager
from core.utils import generate_task_id, human_readable_size, utc_now
from models.response import (
    DubRequest,
    DubResponse,
    ErrorResponse,
    HealthResponse,
    LanguagesResponse,
    RootResponse,
    StatusResponse,
    TaskDeleteResponse,
    TTSEngineInfo,
    TTSEnginesResponse,
    UploadResponse,
    VoicesResponse,
)
from models.task import DubbingTask, TaskStatus
from services.audio_cleaner import AudioCleaner
from services.audio_extractor import AudioExtractor
from services.pipeline import DubbingPipeline
from services.subtitle_service import SubtitleService
from services.transcription_service import TranscriptionService
from services.translation_service import TranslationService
from services.tts_service import TTSService
from services.video_merger import VideoMerger

logger = get_logger(__name__)


# --------------------------------------------------------------------------
# Dependency Container
# --------------------------------------------------------------------------
# Single-process, single-instance wiring. Each object is constructed once
# at import time and reused across every request, which is sufficient for
# a Docker/Render single-container deployment. FastAPI's dependency
# injection (via Depends) is used at the route level to hand these
# shared instances to endpoint functions.
file_manager = FileManager(app_settings=settings)
task_manager = TaskManager(app_settings=settings)
progress_manager = ProgressManager(task_manager=task_manager)

audio_extractor = AudioExtractor(app_settings=settings)
transcription_service = TranscriptionService(app_settings=settings)
translation_service = TranslationService(app_settings=settings)
subtitle_service = SubtitleService(app_settings=settings)
tts_service = TTSService(app_settings=settings)
audio_cleaner = AudioCleaner(app_settings=settings)
video_merger = VideoMerger(app_settings=settings)

dubbing_pipeline = DubbingPipeline(
    task_manager=task_manager,
    progress_manager=progress_manager,
    file_manager=file_manager,
    audio_extractor=audio_extractor,
    transcription_service=transcription_service,
    translation_service=translation_service,
    subtitle_service=subtitle_service,
    tts_service=tts_service,
    audio_cleaner=audio_cleaner,
    video_merger=video_merger,
    app_settings=settings,
)


# --------------------------------------------------------------------------
# Application Lifespan
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Runs startup and shutdown logic around the application's lifetime."""
    settings.ensure_directories()
    task_manager.start_cleanup_scheduler(file_manager)
    logger.info(
        "%s v%s starting up (environment=%s).",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
    )
    yield
    task_manager.stop_cleanup_scheduler()
    logger.info("%s shutting down.", settings.APP_NAME)


# --------------------------------------------------------------------------
# FastAPI Application
# --------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _task_to_status_response(task: DubbingTask) -> StatusResponse:
    """Converts an internal `DubbingTask` into its public `StatusResponse` shape."""
    return StatusResponse(
        task_id=task.task_id,
        status=task.status,
        stage=task.stage.value,
        progress=task.progress,
        message=task.message,
        error_message=task.error_message,
        source_language=task.source_language,
        target_language=task.target_language,
        detected_language=task.detected_language,
        voice=task.voice,
        tts_engine=task.tts_engine,
        original_filename=task.original_filename,
        created_at=task.created_at,
        updated_at=task.updated_at,
        expires_at=task.expires_at,
        download_ready=task.status == TaskStatus.COMPLETED
        and FileManager.file_exists(task.output_video_path),
    )


async def _get_task_or_404(task_id: str) -> DubbingTask:
    """Fetches a task by ID or raises an HTTPException(404)."""
    task = await task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' was not found. It may have expired or never existed.",
        )
    return task


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/", response_model=RootResponse, tags=["General"])
async def root() -> RootResponse:
    """Returns basic service information."""
    return RootResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        docs_url="/docs",
        status="online",
    )


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health() -> HealthResponse:
    """Reports service health, including external binary/config availability."""
    active_tasks = await task_manager.count_active_tasks()

    return HealthResponse(
        status="healthy",
        ffmpeg_available=shutil.which(settings.FFMPEG_BINARY) is not None,
        ffprobe_available=shutil.which(settings.FFPROBE_BINARY) is not None,
        groq_api_key_configured=bool(settings.GROQ_API_KEY),
        active_tasks=active_tasks,
        timestamp=utc_now(),
    )


@app.post("/upload", response_model=UploadResponse, tags=["Dubbing"])
async def upload_video(file: UploadFile) -> UploadResponse:
    """
    Uploads a source video and registers a new dubbing task in PENDING
    status. Call POST /dub next with the returned `task_id` to start
    processing.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided.")

    task_id = generate_task_id(length=settings.TASK_ID_LENGTH)
    saved_path = await file_manager.save_upload_file(file, task_id)
    file_size = FileManager.get_file_size(str(saved_path))

    task = DubbingTask(
        task_id=task_id,
        status=TaskStatus.PENDING,
        original_filename=file.filename,
        video_path=str(saved_path),
    )
    await task_manager.add_task(task)

    logger.info("Upload accepted: task_id=%s filename=%s size=%s", task_id, file.filename, file_size)

    return UploadResponse(
        task_id=task_id,
        original_filename=file.filename,
        file_size_bytes=file_size,
        file_size_readable=human_readable_size(file_size),
        status=task.status,
        message="Video uploaded successfully. Call POST /dub to begin dubbing.",
    )


@app.post("/dub", response_model=DubResponse, tags=["Dubbing"])
async def start_dubbing(request: DubRequest, background_tasks: BackgroundTasks) -> DubResponse:
    """
    Starts the full dubbing pipeline for a previously uploaded video as a
    background task. Poll GET /status/{task_id} to track progress.
    """
    task = await _get_task_or_404(request.task_id)

    if task.status in (TaskStatus.PROCESSING, TaskStatus.QUEUED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task '{request.task_id}' is already {task.status.value}.",
        )

    if not Settings.is_language_supported(request.target_language):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported target language '{request.target_language}'.",
        )

    if request.source_language and not Settings.is_language_supported(request.source_language):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported source language '{request.source_language}'.",
        )

    resolved_engine = request.tts_engine or settings.DEFAULT_TTS_ENGINE

    if request.tts_engine and not tts_service.is_engine_registered(request.tts_engine):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown tts_engine '{request.tts_engine}'. "
                "See GET /tts/engines for the list of registered engines."
            ),
        )

    # This voice/language cross-check is scoped to the "edge" engine because
    # it validates against EDGE_TTS_ALL_VOICES specifically; other engines
    # (Azure, ElevenLabs, Piper, XTTS) use their own voice catalogs and are
    # validated by the engine itself at synthesis time instead.
    if (
        request.voice
        and resolved_engine == "edge"
        and not Settings.is_voice_valid_for_language(request.target_language, request.voice)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Voice '{request.voice}' is not available for language '{request.target_language}'.",
        )

    task.target_language = request.target_language
    task.source_language = request.source_language
    task.voice = request.voice
    task.tts_engine = request.tts_engine
    task.status = TaskStatus.QUEUED
    await task_manager.update_task(task)

    background_tasks.add_task(dubbing_pipeline.run, task.task_id, request.burn_subtitles)

    logger.info(
        "Dubbing started: task_id=%s target_language=%s source_language=%s voice=%s tts_engine=%s",
        task.task_id,
        request.target_language,
        request.source_language,
        request.voice,
        resolved_engine,
    )

    return DubResponse(
        task_id=task.task_id,
        status=task.status,
        stage=task.stage.value,
        message="Dubbing pipeline started. Poll GET /status/{task_id} for progress.",
    )


@app.get("/status/{task_id}", response_model=StatusResponse, tags=["Dubbing"])
async def get_status(task_id: str) -> StatusResponse:
    """Returns the current status, stage, and progress percentage of a task."""
    task = await _get_task_or_404(task_id)
    return _task_to_status_response(task)


@app.get("/download/{task_id}", tags=["Dubbing"])
async def download_video(task_id: str) -> FileResponse:
    """Downloads the finished dubbed video for a completed task."""
    task = await _get_task_or_404(task_id)

    if task.status != TaskStatus.COMPLETED or not FileManager.file_exists(task.output_video_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task '{task_id}' is not yet complete (current status: {task.status.value}).",
        )

    download_filename = f"dubbed_{task.original_filename}"
    return FileResponse(
        path=task.output_video_path,  # type: ignore[arg-type]
        media_type="video/mp4",
        filename=download_filename,
    )


@app.delete("/task/{task_id}", response_model=TaskDeleteResponse, tags=["Dubbing"])
async def delete_task(task_id: str) -> TaskDeleteResponse:
    """Deletes a task and every file associated with it."""
    deleted = await task_manager.delete_task(task_id, file_manager)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' was not found.",
        )

    return TaskDeleteResponse(task_id=task_id, deleted=True, message="Task and all associated files were deleted.")


@app.get("/languages", response_model=LanguagesResponse, tags=["Reference"])
async def list_languages() -> LanguagesResponse:
    """Returns every language code the platform supports, with display names."""
    return LanguagesResponse(languages=SUPPORTED_LANGUAGES, count=len(SUPPORTED_LANGUAGES))


@app.get("/voices", response_model=VoicesResponse, tags=["Reference"])
async def list_voices(language: Optional[str] = None) -> VoicesResponse:
    """
    Returns available Edge TTS voices. If `language` is provided, only that
    language's voices are returned; otherwise every language's voices are
    returned.
    """
    if language:
        if not Settings.is_language_supported(language):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language '{language}'.",
            )
        voices: Dict[str, List[str]] = {language: Settings.get_available_voices(language)}
    else:
        voices = EDGE_TTS_ALL_VOICES

    return VoicesResponse(language=language, voices=voices)


@app.get("/tts/engines", response_model=TTSEnginesResponse, tags=["Reference"])
async def list_tts_engines() -> TTSEnginesResponse:
    """
    Returns every registered TTS engine with its live availability and
    capability flags (voice selection, voice cloning, streaming, multi
    speaker support), plus which engine is currently configured as the
    default and as the automatic fallback.
    """
    engine_healths = await tts_service.list_engines()

    return TTSEnginesResponse(
        engines=[
            TTSEngineInfo(
                name=health.name,
                available=health.available,
                detail=health.detail,
                is_default=health.name == settings.DEFAULT_TTS_ENGINE,
                fallback_rank=health.fallback_rank,
                supports_voice_selection=health.supports_voice_selection,
                supports_voice_cloning=health.supports_voice_cloning,
                supports_streaming=health.supports_streaming,
                supports_multi_speaker=health.supports_multi_speaker,
            )
            for health in engine_healths
        ],
        default_engine=settings.DEFAULT_TTS_ENGINE,
        fallback_order=settings.get_fallback_engines(),
    )


# --------------------------------------------------------------------------
# Exception Handling
# --------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception):  # type: ignore[no-untyped-def]
    """Catches any exception not already handled, logging it and returning a clean 500."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_server_error",
            detail="An unexpected error occurred. Please try again or contact support.",
        ).model_dump(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=settings.HOST, port=settings.PORT, reload=not settings.is_production)

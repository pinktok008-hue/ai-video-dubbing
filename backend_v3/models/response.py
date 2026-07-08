"""
models/response.py
=====================
Pydantic response schemas returned by the FastAPI endpoints in app.py.
Keeping these separate from `models/task.py` (the internal domain model)
lets the internal representation evolve without breaking the public API
contract.

Python: 3.12
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.task import TaskStatus


class RootResponse(BaseModel):
    """Response for GET /"""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    description: str
    docs_url: str
    status: str = "online"


class HealthResponse(BaseModel):
    """Response for GET /health"""

    model_config = ConfigDict(extra="forbid")

    status: str
    ffmpeg_available: bool
    ffprobe_available: bool
    groq_api_key_configured: bool
    active_tasks: int
    timestamp: datetime


class UploadResponse(BaseModel):
    """Response for POST /upload"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    original_filename: str
    file_size_bytes: int
    file_size_readable: str
    status: TaskStatus
    message: str


class DubRequest(BaseModel):
    """Request body for POST /dub"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="Task ID returned by POST /upload.")
    target_language: str = Field(..., description="ISO code of the language to dub into.")
    source_language: Optional[str] = Field(
        default=None, description="ISO code of the source language. Auto-detected if omitted."
    )
    voice: Optional[str] = Field(
        default=None, description="Specific Edge TTS voice name. Defaults to the language's default voice."
    )
    burn_subtitles: bool = Field(
        default=False, description="If true, embed subtitles as a soft subtitle stream in the output."
    )


class DubResponse(BaseModel):
    """Response for POST /dub"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: TaskStatus
    stage: str
    message: str


class StatusResponse(BaseModel):
    """Response for GET /status/{task_id}"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: TaskStatus
    stage: str
    progress: int
    message: str
    error_message: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    detected_language: Optional[str] = None
    voice: Optional[str] = None
    original_filename: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    download_ready: bool


class TaskDeleteResponse(BaseModel):
    """Response for DELETE /task/{task_id}"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    deleted: bool
    message: str


class LanguagesResponse(BaseModel):
    """Response for GET /languages"""

    model_config = ConfigDict(extra="forbid")

    languages: Dict[str, str]
    count: int


class VoicesResponse(BaseModel):
    """Response for GET /voices"""

    model_config = ConfigDict(extra="forbid")

    language: Optional[str]
    voices: Dict[str, List[str]]


class ErrorResponse(BaseModel):
    """Generic error envelope used by exception handlers."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
    task_id: Optional[str] = None

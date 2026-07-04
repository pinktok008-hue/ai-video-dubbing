import os
from pathlib import Path

# ===========================
# Base Directory
# ===========================

BASE_DIR = Path(__file__).resolve().parent

# ===========================
# Project Directories
# ===========================

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_DIR = BASE_DIR / "audio"
TEMP_DIR = BASE_DIR / "temp"

# Automatically create folders
for directory in [
    UPLOAD_DIR,
    OUTPUT_DIR,
    AUDIO_DIR,
    TEMP_DIR
]:
    directory.mkdir(parents=True, exist_ok=True)

# ===========================
# File Upload Settings
# ===========================

MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024   # 5GB

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm"
}

# ===========================
# Render Settings
# ===========================

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 5000))

# ===========================
# Progress
# ===========================

PROGRESS_UPDATE_INTERVAL = 1

# ===========================
# Cleanup
# ===========================

AUTO_DELETE_TEMP = True

AUTO_DELETE_AFTER_HOURS = 24

# ===========================
# Logging
# ===========================

LOG_LEVEL = "INFO"

LOG_FOLDER = BASE_DIR / "logs"

LOG_FOLDER.mkdir(exist_ok=True)

# ===========================
# AI Services
# ===========================

ENABLE_WHISPER = False

ENABLE_TRANSLATION = False

ENABLE_VOICE_CLONE = False

ENABLE_LIPSYNC = False

ENABLE_SUBTITLE = False

ENABLE_BGM = False

# ===========================
# Future GPU
# ===========================

GPU_ENABLED = False

GPU_DEVICE = "cuda"

CPU_THREADS = os.cpu_count()

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

STORAGE_DIR = BASE_DIR / "storage"

UPLOAD_FOLDER = STORAGE_DIR / "uploads"

OUTPUT_FOLDER = STORAGE_DIR / "outputs"

AUDIO_FOLDER = STORAGE_DIR / "audio"

TEMP_FOLDER = STORAGE_DIR / "temp"

SUBTITLE_FOLDER = STORAGE_DIR / "subtitles"

for folder in [
    STORAGE_DIR,
    UPLOAD_FOLDER,
    OUTPUT_FOLDER,
    AUDIO_FOLDER,
    TEMP_FOLDER,
    SUBTITLE_FOLDER,
]:
    folder.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

DEFAULT_LANGUAGE = os.getenv(
    "DEFAULT_LANGUAGE",
    "Hindi"
)

DEFAULT_VOICE = os.getenv(
    "DEFAULT_VOICE",
    "en-US-AndrewNeural"
)

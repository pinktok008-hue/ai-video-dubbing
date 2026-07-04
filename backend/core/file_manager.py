"""
AI Video Dubbing Platform
Version : 2.0

File Manager
"""

import shutil
from pathlib import Path
from typing import Optional

from config import (
    UPLOAD_DIR,
    OUTPUT_DIR,
    AUDIO_DIR,
    TEMP_DIR,
    ALLOWED_VIDEO_EXTENSIONS
)


class FileManager:

    @staticmethod
    def ensure_directories():

        for folder in [
            UPLOAD_DIR,
            OUTPUT_DIR,
            AUDIO_DIR,
            TEMP_DIR
        ]:
            folder.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------

    @staticmethod
    def get_extension(filename: str):

        return Path(filename).suffix.lower()

    # ---------------------------------------

    @staticmethod
    def is_allowed_video(filename: str):

        return (
            FileManager.get_extension(filename)
            in
            ALLOWED_VIDEO_EXTENSIONS
        )

    # ---------------------------------------

    @staticmethod
    def upload_path(filename: str):

        return UPLOAD_DIR / filename

    # ---------------------------------------

    @staticmethod
    def audio_path(filename: str):

        return AUDIO_DIR / filename

    # ---------------------------------------

    @staticmethod
    def output_path(filename: str):

        return OUTPUT_DIR / filename

    # ---------------------------------------

    @staticmethod
    def temp_path(filename: str):

        return TEMP_DIR / filename

    # ---------------------------------------

    @staticmethod
    def delete(path: Optional[Path]):

        if path is None:
            return

        if path.exists():

            if path.is_file():
                path.unlink()

            elif path.is_dir():
                shutil.rmtree(path)

    # ---------------------------------------

    @staticmethod
    def size(path: Path):

        if not path.exists():
            return 0

        return path.stat().st_size

    # ---------------------------------------

    @staticmethod
    def exists(path: Path):

        return path.exists()

    # ---------------------------------------

    @staticmethod
    def clear_temp():

        if not TEMP_DIR.exists():
            return

        for item in TEMP_DIR.iterdir():

            FileManager.delete(item)


file_manager = FileManager()

file_manager.ensure_directories()

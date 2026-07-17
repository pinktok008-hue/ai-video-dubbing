"""
config.py
=========
Centralized configuration module for the AI Video Dubbing Platform V3.

This module is the single source of truth for:
    - Application metadata
    - Filesystem paths (storage layout)
    - Third-party service configuration (Groq Whisper, Edge TTS, FFmpeg)
    - Upload / processing constraints
    - Task lifecycle & cleanup configuration
    - Logging configuration
    - Supported languages & voice mappings
    - Pipeline stage definitions

Every other module in this project imports its configuration from here.
No other module should hardcode paths, timeouts, language codes, or
voice names -- they must be added/looked up in this file so the system
stays consistent and easy to extend (e.g. Voice Cloning, XTTS, RVC,
Speaker Detection, Multi Speaker, Lip Sync, Emotion TTS in the future).

Python: 3.12
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# --------------------------------------------------------------------------
# Pipeline Stage Definitions
# --------------------------------------------------------------------------
class PipelineStage(str, Enum):
    """
    Enumerates every stage of the dubbing pipeline in execution order.
    Used by ProgressManager / TaskManager to report granular progress
    and by the pipeline orchestrator to know what stage comes next.
    """

    QUEUED = "queued"
    UPLOAD = "upload"
    AUDIO_EXTRACTION = "audio_extraction"
    TRANSCRIPTION = "transcription"
    TRANSLATION = "translation"
    SUBTITLE_GENERATION = "subtitle_generation"
    TTS_GENERATION = "tts_generation"
    AUDIO_CLEANUP = "audio_cleanup"
    AUDIO_MERGE = "audio_merge"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def ordered_stages(cls) -> List["PipelineStage"]:
        """Returns the processing stages in strict execution order."""
        return [
            cls.QUEUED,
            cls.UPLOAD,
            cls.AUDIO_EXTRACTION,
            cls.TRANSCRIPTION,
            cls.TRANSLATION,
            cls.SUBTITLE_GENERATION,
            cls.TTS_GENERATION,
            cls.AUDIO_CLEANUP,
            cls.AUDIO_MERGE,
            cls.FINALIZING,
            cls.COMPLETED,
        ]

    @classmethod
    def progress_percentage(cls, stage: "PipelineStage") -> int:
        """
        Maps a pipeline stage to an approximate overall progress percentage.
        Used by ProgressManager to report a single numeric progress value
        to API consumers.
        """
        mapping: Dict[PipelineStage, int] = {
            cls.QUEUED: 0,
            cls.UPLOAD: 5,
            cls.AUDIO_EXTRACTION: 15,
            cls.TRANSCRIPTION: 35,
            cls.TRANSLATION: 50,
            cls.SUBTITLE_GENERATION: 60,
            cls.TTS_GENERATION: 75,
            cls.AUDIO_CLEANUP: 85,
            cls.AUDIO_MERGE: 95,
            cls.FINALIZING: 98,
            cls.COMPLETED: 100,
            cls.FAILED: 100,
        }
        return mapping.get(stage, 0)


# --------------------------------------------------------------------------
# Static Data: Supported Languages
# --------------------------------------------------------------------------
# Language codes are compatible with both `deep-translator` (Google Translate
# backend) and used as lookup keys into EDGE_TTS_VOICE_MAP below.
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-CN": "Chinese (Simplified)",
    "ar": "Arabic",
    "bn": "Bengali",
    "ur": "Urdu",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "nl": "Dutch",
    "pl": "Polish",
    "uk": "Ukrainian",
    "el": "Greek",
    "he": "Hebrew",
    "sv": "Swedish",
    "fi": "Finnish",
    "no": "Norwegian",
    "da": "Danish",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "fa": "Persian",
    "sw": "Swahili",
    "ms": "Malay",
    "fil": "Filipino",
}


# --------------------------------------------------------------------------
# Static Data: Edge TTS Voice Mapping
# --------------------------------------------------------------------------
# Default voice used per language when the caller does not request a
# specific voice. These map 1:1 with Microsoft Edge TTS neural voice names.
EDGE_TTS_VOICE_MAP: Dict[str, str] = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ar": "ar-SA-ZariyahNeural",
    "bn": "bn-IN-TanishaaNeural",
    "ur": "ur-PK-UzmaNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "mr": "mr-IN-AarohiNeural",
    "gu": "gu-IN-DhwaniNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "pa": "hi-IN-SwaraNeural",  # no native Punjabi Edge TTS voice; falls back to Hindi
    "tr": "tr-TR-EmelNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "th": "th-TH-PremwadeeNeural",
    "id": "id-ID-GadisNeural",
    "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-ZofiaNeural",
    "uk": "uk-UA-PolinaNeural",
    "el": "el-GR-AthinaNeural",
    "he": "he-IL-HilaNeural",
    "sv": "sv-SE-SofieNeural",
    "fi": "fi-FI-SelmaNeural",
    "no": "nb-NO-PernilleNeural",
    "da": "da-DK-ChristelNeural",
    "cs": "cs-CZ-VlastaNeural",
    "ro": "ro-RO-AlinaNeural",
    "hu": "hu-HU-NoemiNeural",
    "fa": "fa-IR-DilaraNeural",
    "sw": "sw-KE-ZuriNeural",
    "ms": "ms-MY-YasminNeural",
    "fil": "fil-PH-BlessicaNeural",
}


# Additional alternative voices per language (male/female variety) exposed
# via GET /voices so the frontend can offer a voice picker. Every language
# in SUPPORTED_LANGUAGES has at least one entry (its default voice).
EDGE_TTS_ALL_VOICES: Dict[str, List[str]] = {
    "en": ["en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-GB-RyanNeural"],
    "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
    "es": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural", "es-MX-DaliaNeural"],
    "fr": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
    "de": ["de-DE-KatjaNeural", "de-DE-ConradNeural"],
    "it": ["it-IT-ElsaNeural", "it-IT-DiegoNeural"],
    "pt": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
    "ru": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
    "ja": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "ko": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    "zh-CN": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
    "ar": ["ar-SA-ZariyahNeural", "ar-SA-HamedNeural"],
    "bn": ["bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"],
    "ur": ["ur-PK-UzmaNeural", "ur-PK-AsadNeural"],
    "ta": ["ta-IN-PallaviNeural", "ta-IN-ValluvarNeural"],
    "te": ["te-IN-ShrutiNeural", "te-IN-MohanNeural"],
    "mr": ["mr-IN-AarohiNeural", "mr-IN-ManoharNeural"],
    "gu": ["gu-IN-DhwaniNeural", "gu-IN-NiranjanNeural"],
    "kn": ["kn-IN-SapnaNeural", "kn-IN-GaganNeural"],
    "ml": ["ml-IN-SobhanaNeural", "ml-IN-MidhunNeural"],
    "pa": ["hi-IN-SwaraNeural"],
    "tr": ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"],
    "vi": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"],
    "th": ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"],
    "id": ["id-ID-GadisNeural", "id-ID-ArdiNeural"],
    "nl": ["nl-NL-ColetteNeural", "nl-NL-MaartenNeural"],
    "pl": ["pl-PL-ZofiaNeural", "pl-PL-MarekNeural"],
    "uk": ["uk-UA-PolinaNeural", "uk-UA-OstapNeural"],
    "el": ["el-GR-AthinaNeural", "el-GR-NestorasNeural"],
    "he": ["he-IL-HilaNeural", "he-IL-AvriNeural"],
    "sv": ["sv-SE-SofieNeural", "sv-SE-MattiasNeural"],
    "fi": ["fi-FI-SelmaNeural", "fi-FI-HarriNeural"],
    "no": ["nb-NO-PernilleNeural", "nb-NO-FinnNeural"],
    "da": ["da-DK-ChristelNeural", "da-DK-JeppeNeural"],
    "cs": ["cs-CZ-VlastaNeural", "cs-CZ-AntoninNeural"],
    "ro": ["ro-RO-AlinaNeural", "ro-RO-EmilNeural"],
    "hu": ["hu-HU-NoemiNeural", "hu-HU-TamasNeural"],
    "fa": ["fa-IR-DilaraNeural", "fa-IR-FaridNeural"],
    "sw": ["sw-KE-ZuriNeural", "sw-KE-RafikiNeural"],
    "ms": ["ms-MY-YasminNeural", "ms-MY-OsmanNeural"],
    "fil": ["fil-PH-BlessicaNeural", "fil-PH-AngeloNeural"],
}


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables (and an
    optional `.env` file for local development). All paths are resolved to
    absolute `Path` objects rooted at the project's `backend_v3/` directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------
    # Application Metadata
    # ---------------------------------------------------------------
    APP_NAME: str = "AI Video Dubbing Platform"
    APP_VERSION: str = "3.0.0"
    APP_DESCRIPTION: str = (
        "Production-ready AI Video Dubbing Platform: upload, transcribe, "
        "translate, generate subtitles, synthesize speech, and re-render "
        "dubbed videos end-to-end."
    )
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")  # "development" | "production"

    # ---------------------------------------------------------------
    # Server
    # ---------------------------------------------------------------
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    CORS_ORIGINS: str = Field(default="*")  # comma-separated list or "*"

    # ---------------------------------------------------------------
    # Filesystem Layout
    # ---------------------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = STORAGE_DIR / "uploads"
    OUTPUT_DIR: Path = STORAGE_DIR / "outputs"
    AUDIO_DIR: Path = STORAGE_DIR / "audio"
    TEMP_DIR: Path = STORAGE_DIR / "temp"
    SUBTITLE_DIR: Path = STORAGE_DIR / "subtitles"
    LOG_DIR: Path = STORAGE_DIR / "logs"
    TASK_STATE_DIR: Path = STORAGE_DIR / "task_state"

    # ---------------------------------------------------------------
    # Upload Constraints
    # ---------------------------------------------------------------
    MAX_UPLOAD_SIZE_MB: int = Field(default=500)
    ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}
    UPLOAD_CHUNK_SIZE_BYTES: int = Field(default=1024 * 1024)  # 1 MB

    # ---------------------------------------------------------------
    # Groq Whisper (Speech-to-Text)
    # ---------------------------------------------------------------
    GROQ_API_KEY: str = Field(default="")
    GROQ_API_BASE_URL: str = Field(default="https://api.groq.com/openai/v1")
    GROQ_WHISPER_MODEL: str = Field(default="whisper-large-v3")
    GROQ_REQUEST_TIMEOUT_SECONDS: int = Field(default=180)
    GROQ_MAX_RETRIES: int = Field(default=3)
    GROQ_RETRY_BACKOFF_SECONDS: float = Field(default=2.0)

    # ---------------------------------------------------------------
    # Translation
    # ---------------------------------------------------------------
    TRANSLATION_PROVIDER: str = Field(default="google")  # deep-translator backend
    TRANSLATION_MAX_RETRIES: int = Field(default=3)
    TRANSLATION_RETRY_BACKOFF_SECONDS: float = Field(default=1.5)
    TRANSLATION_CHUNK_CHAR_LIMIT: int = Field(default=4500)

    # ---------------------------------------------------------------
    # Edge TTS
    # ---------------------------------------------------------------
    EDGE_TTS_DEFAULT_RATE: str = Field(default="+0%")
    EDGE_TTS_DEFAULT_VOLUME: str = Field(default="+0%")
    EDGE_TTS_DEFAULT_PITCH: str = Field(default="+0Hz")
    EDGE_TTS_TIMEOUT_SECONDS: int = Field(default=120)
    EDGE_TTS_MAX_RETRIES: int = Field(default=3)

    # ---------------------------------------------------------------
    # Multi-Engine TTS (V3.1 LTS)
    # ---------------------------------------------------------------
    # Registered engine names: gtts | edge | azure | piper | xtts | elevenlabs
    # (see services/tts/engines/__init__.py for the authoritative registry).
    #
    # DEFAULT_TTS_ENGINE is gtts: it needs no API key, no binary, and no
    # downloaded model, so a fresh deployment with zero configuration can
    # still synthesize speech immediately. Edge, Azure, Piper, XTTS, and
    # ElevenLabs are all optional engines, selectable per-request via
    # POST /dub's `tts_engine` field.
    #
    # FALLBACK_TTS_ENGINES is a comma-separated, ORDERED list (not a single
    # engine) -- e.g. "edge,azure,piper,xtts,elevenlabs" -- tried in order,
    # left to right, until one succeeds or the list is exhausted. Stored as
    # a plain string rather than a native list specifically so parsing does
    # not depend on pydantic-settings' JSON-vs-delimited env-var parsing
    # behavior; see `get_fallback_engines()` below.
    DEFAULT_TTS_ENGINE: str = Field(default="gtts")
    FALLBACK_TTS_ENGINES: str = Field(default="edge,azure,piper,xtts,elevenlabs")
    TTS_PARALLEL_WORKERS: int = Field(default=4)

    # --- gTTS ---
    GTTS_DEFAULT_TLD: str = Field(default="com")
    GTTS_SLOW: bool = Field(default=False)
    GTTS_TIMEOUT_SECONDS: int = Field(default=30)
    GTTS_MAX_RETRIES: int = Field(default=3)

    # --- Azure Cognitive Services Speech ---
    AZURE_SPEECH_KEY: str = Field(default="")
    AZURE_SPEECH_REGION: str = Field(default="")
    AZURE_TTS_TIMEOUT_SECONDS: int = Field(default=30)

    # --- ElevenLabs ---
    ELEVENLABS_API_KEY: str = Field(default="")
    ELEVENLABS_DEFAULT_VOICE_ID: str = Field(default="")
    ELEVENLABS_MODEL_ID: str = Field(default="eleven_multilingual_v2")
    ELEVENLABS_STABILITY: float = Field(default=0.5)
    ELEVENLABS_SIMILARITY_BOOST: float = Field(default=0.75)
    ELEVENLABS_TIMEOUT_SECONDS: int = Field(default=60)

    # --- Piper (local; optional, see requirements-optional.txt) ---
    PIPER_BINARY_PATH: str = Field(default="piper")
    PIPER_MODEL_DIR: Path = STORAGE_DIR / "tts_models" / "piper"
    PIPER_VOICE_MODEL_MAP: Dict[str, str] = Field(default_factory=dict)
    PIPER_TIMEOUT_SECONDS: int = Field(default=60)

    # --- XTTS v2 / Coqui (local; optional, see requirements-optional.txt) ---
    XTTS_MODEL_NAME: str = Field(default="tts_models/multilingual/multi-dataset/xtts_v2")
    XTTS_DEVICE: str = Field(default="cpu")
    XTTS_DEFAULT_SPEAKER_WAV: str = Field(default="")
    XTTS_TIMEOUT_SECONDS: int = Field(default=180)

    def get_fallback_engines(self) -> List[str]:
        """
        Parses `FALLBACK_TTS_ENGINES` (a comma-separated string, e.g.
        "edge,azure,piper,xtts,elevenlabs") into an ordered list of
        engine names, trimming whitespace and dropping empty entries.
        Order is preserved -- this is the sequence `TTSEngineManager`
        tries engines in after the primary engine fails or is unavailable.
        """
        return [name.strip() for name in self.FALLBACK_TTS_ENGINES.split(",") if name.strip()]

    # ---------------------------------------------------------------
    # FFmpeg
    # ---------------------------------------------------------------
    FFMPEG_BINARY: str = Field(default="ffmpeg")
    FFPROBE_BINARY: str = Field(default="ffprobe")
    FFMPEG_THREADS: int = Field(default=0)  # 0 = let ffmpeg auto-detect
    FFMPEG_TIMEOUT_SECONDS: int = Field(default=1800)
    EXTRACTED_AUDIO_SAMPLE_RATE: int = Field(default=16000)
    EXTRACTED_AUDIO_CHANNELS: int = Field(default=1)
    EXTRACTED_AUDIO_CODEC: str = Field(default="pcm_s16le")
    OUTPUT_VIDEO_CODEC: str = Field(default="libx264")
    OUTPUT_AUDIO_CODEC: str = Field(default="aac")
    OUTPUT_VIDEO_CRF: int = Field(default=20)
    OUTPUT_VIDEO_PRESET: str = Field(default="medium")
    OUTPUT_AUDIO_BITRATE: str = Field(default="192k")

    # ---------------------------------------------------------------
    # Audio Processing Module (Sprint 2)
    # ---------------------------------------------------------------
    # Every stylistic DSP stage below defaults to disabled, so an
    # unmodified deployment produces exactly the audio it always has.
    # TIMELINE_ALIGNMENT_ENABLED defaults to True: it is a direct,
    # evidence-based mitigation for a real, previously-documented issue
    # (translated speech overrunning its segment window causes audible
    # overlap -- see MIGRATION_V3.1.md and the audio pipeline audit),
    # not a stylistic choice, so it ships on with a conservative bound.

    # --- Silence trimming (applied per synthesized clip) ---
    SILENCE_TRIM_ENABLED: bool = Field(default=False)
    SILENCE_TRIM_THRESHOLD_DB: float = Field(default=-45.0)
    SILENCE_TRIM_MIN_DURATION_SECONDS: float = Field(default=0.05)

    # --- Fade in/out (applied per synthesized clip) ---
    FADE_ENABLED: bool = Field(default=False)
    FADE_IN_SECONDS: float = Field(default=0.02)
    FADE_OUT_SECONDS: float = Field(default=0.05)

    # --- Loudness normalization / volume matching (applied per clip, to
    #     make different TTS engines' naturally-different output levels
    #     consistent before mixing) ---
    LOUDNESS_NORMALIZATION_ENABLED: bool = Field(default=False)
    LOUDNESS_TARGET_LUFS: float = Field(default=-16.0)
    LOUDNESS_TRUE_PEAK_DBFS: float = Field(default=-1.5)
    LOUDNESS_RANGE_LU: float = Field(default=11.0)

    # --- Noise gate (applied per clip) ---
    NOISE_GATE_ENABLED: bool = Field(default=False)
    NOISE_GATE_THRESHOLD_DB: float = Field(default=-50.0)
    NOISE_GATE_RATIO: float = Field(default=2.0)

    # --- Click / pop reduction (applied per clip) ---
    CLICK_REDUCTION_ENABLED: bool = Field(default=False)

    # --- Peak limiter (applied once, to the final assembled track) ---
    PEAK_LIMITER_ENABLED: bool = Field(default=False)
    PEAK_LIMITER_CEILING_DBFS: float = Field(default=-1.0)

    # --- Dynamic range compression (applied once, to the final track) ---
    DYNAMIC_COMPRESSION_ENABLED: bool = Field(default=False)
    COMPRESSOR_THRESHOLD_DB: float = Field(default=-20.0)
    COMPRESSOR_RATIO: float = Field(default=3.0)
    COMPRESSOR_ATTACK_MS: float = Field(default=5.0)
    COMPRESSOR_RELEASE_MS: float = Field(default=150.0)

    # --- Equalizer (applied once, to the final track) ---
    EQUALIZER_ENABLED: bool = Field(default=False)
    EQUALIZER_HIGHPASS_HZ: float = Field(default=80.0)
    EQUALIZER_LOWPASS_HZ: float = Field(default=12000.0)
    EQUALIZER_PRESENCE_BOOST_HZ: float = Field(default=3000.0)
    EQUALIZER_PRESENCE_BOOST_DB: float = Field(default=0.0)

    # --- Timeline alignment: fit each clip to its segment window via
    #     bounded time-stretch (ffmpeg `atempo`) rather than letting an
    #     overlong clip overlap the next segment ---
    TIMELINE_ALIGNMENT_ENABLED: bool = Field(default=True)
    TIMELINE_MAX_TIME_STRETCH: float = Field(default=1.20)
    TIMELINE_MIN_GAP_SECONDS: float = Field(default=0.05)

    # --- Audio ducking: Part 4's fallback for when true source
    #     separation is unavailable (always, on Render Free) -- attenuate
    #     the ORIGINAL audio under dubbed speech instead of discarding it ---
    AUDIO_DUCKING_ENABLED: bool = Field(default=False)
    AUDIO_DUCKING_LEVEL_DB: float = Field(default=-18.0)
    AUDIO_DUCKING_FADE_SECONDS: float = Field(default=0.15)

    def get_enabled_segment_filters_summary(self) -> Dict[str, bool]:
        """Introspection helper for logging/diagnostics: which per-clip DSP stages are active."""
        return {
            "silence_trim": self.SILENCE_TRIM_ENABLED,
            "fade": self.FADE_ENABLED,
            "loudness_normalization": self.LOUDNESS_NORMALIZATION_ENABLED,
            "noise_gate": self.NOISE_GATE_ENABLED,
            "click_reduction": self.CLICK_REDUCTION_ENABLED,
        }

    # ---------------------------------------------------------------
    # Task Lifecycle & Cleanup
    # ---------------------------------------------------------------
    TASK_EXPIRY_HOURS: int = Field(default=24)
    TASK_CLEANUP_INTERVAL_MINUTES: int = Field(default=30)
    TASK_MAX_CONCURRENT: int = Field(default=3)
    TASK_ID_LENGTH: int = Field(default=12)

    # ---------------------------------------------------------------
    # Logging
    # ---------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    LOG_FILE_NAME: str = Field(default="app.log")
    LOG_FILE_MAX_BYTES: int = Field(default=10 * 1024 * 1024)  # 10 MB
    LOG_FILE_BACKUP_COUNT: int = Field(default=5)
    LOG_TO_CONSOLE: bool = Field(default=True)

    # -----------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------
    @field_validator("GROQ_API_KEY", mode="before")
    @classmethod
    def _empty_string_if_none(cls, value: Optional[str]) -> str:
        return value or ""

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return str(value).upper()

    # -----------------------------------------------------------------
    # Derived / Convenience Properties
    # -----------------------------------------------------------------
    @property
    def cors_origins_list(self) -> List[str]:
        """Returns CORS_ORIGINS as a list, expanding '*' to a wildcard list."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Returns MAX_UPLOAD_SIZE_MB converted to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    # -----------------------------------------------------------------
    # Directory Management
    # -----------------------------------------------------------------
    def ensure_directories(self) -> None:
        """
        Creates every storage directory required by the platform if it
        does not already exist. Must be called once at application
        startup (see app.py lifespan handler) before any service writes
        to disk.
        """
        required_dirs: List[Path] = [
            self.STORAGE_DIR,
            self.UPLOAD_DIR,
            self.OUTPUT_DIR,
            self.AUDIO_DIR,
            self.TEMP_DIR,
            self.SUBTITLE_DIR,
            self.LOG_DIR,
            self.PIPER_MODEL_DIR,  # Created even if unused; only populated if an operator adopts Piper.
            self.TASK_STATE_DIR,
        ]
        for directory in required_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # Language / Voice Helpers
    # -----------------------------------------------------------------
    @staticmethod
    def is_language_supported(language_code: str) -> bool:
        """Checks whether a language code is supported by the platform."""
        return language_code in SUPPORTED_LANGUAGES

    @staticmethod
    def get_language_name(language_code: str) -> Optional[str]:
        """Returns the human-readable name for a supported language code."""
        return SUPPORTED_LANGUAGES.get(language_code)

    @staticmethod
    def get_default_voice(language_code: str) -> str:
        """
        Returns the default neural voice name for a given language code.
        Falls back to the English default voice if the language has no
        explicit mapping, ensuring TTS synthesis never fails outright
        due to a missing voice entry.

        Used by both the Edge and Azure TTS engines: Azure Neural TTS
        shares the same underlying voice catalog as Edge (e.g.
        "en-US-AriaNeural" resolves on both), so this one mapping table
        serves as a sensible default for either engine.
        """
        return EDGE_TTS_VOICE_MAP.get(language_code, EDGE_TTS_VOICE_MAP["en"])

    @staticmethod
    def get_available_voices(language_code: str) -> List[str]:
        """
        Returns all available Edge TTS voice options for a given language
        code. Falls back to the English voice list if unmapped.
        """
        return EDGE_TTS_ALL_VOICES.get(language_code, EDGE_TTS_ALL_VOICES["en"])

    @staticmethod
    def is_voice_valid_for_language(language_code: str, voice_name: str) -> bool:
        """Validates that a requested voice name belongs to the given language."""
        return voice_name in Settings.get_available_voices(language_code)


# --------------------------------------------------------------------------
# Cached Settings Accessor
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached, process-wide singleton instance of `Settings`.

    Using `lru_cache` guarantees the environment is parsed exactly once and
    every module in the application shares the same configuration object,
    avoiding repeated environment lookups and inconsistent state.
    """
    settings = Settings()
    settings.ensure_directories()
    return settings


# A module-level singleton for convenient `from config import settings` imports.
settings: Settings = get_settings()

# AI Video Dubbing Platform V3.2 LTS
## Production Specification

## Goal

Build a production-ready AI Video Dubbing Platform that runs on Render Free Plan by default while keeping the architecture future-proof for premium features.

The platform must preserve the original background music and sound effects while replacing only spoken dialogue with translated speech.

The project must use a modular architecture where every service is independent and easily replaceable.

---

# Core Requirements

- FastAPI backend
- Python 3.12
- FFmpeg
- FFprobe
- Groq Whisper
- deep-translator
- Multiple TTS Engine Architecture
- Render Free compatible
- Production-ready code
- Fully modular
- No duplicate logic
- No dead code
- Complete error handling
- Logging
- Retry system
- Health checks

---

# Supported TTS Engines

Default:

- gTTS

Optional:

- Edge TTS
- Azure Speech
- Piper
- XTTS
- ElevenLabs

Architecture must allow future engines without changing pipeline code.

---

# Engine Fallback

Configurable fallback chain.

Example

gTTS

↓

Edge

↓

Azure

↓

Piper

↓

XTTS

↓

ElevenLabs

Automatic fallback when an engine fails.

Unavailable engines must be skipped automatically.

---

# Voice Processing

Every engine output must pass through the same audio enhancement pipeline.

Pipeline includes

- Loudness normalization
- Silence trimming
- Fade in
- Fade out
- Compressor
- Limiter
- EQ
- Volume balancing
- Noise cleanup (voice only)
- Sample rate normalization
- Bitrate normalization

Every engine must produce consistent output quality.

---

# Voice Selection

If an engine supports voice selection

Use requested voice.

If not

Ignore voice safely.

Never fail because voice selection is unsupported.

---

# Voice Overlap Fix

Current overlapping speech issue must be completely fixed.

Speech timing must be aligned.

Long speech must never overlap with next dialogue.

Handle

- speech stretching
- silence insertion
- gap correction
- duration alignment

---

# Background Music Preservation

Original BGM must remain.

Original SFX must remain.

Only spoken dialogue should be replaced.

Do not mute entire audio.

Dialogue separation must be modular for future upgrades.

Current implementation may use audio ducking where required.

Architecture must support future AI source separation.

---

# Subtitle

Generate

Original subtitles

Translated subtitles

Support

SRT

Future support

ASS

VTT

---

# Translation

Support

Auto language detection

Manual language

Segment translation

Retry

Validation

---

# Long Video Support

Support videos up to

2 hours

Pipeline must avoid loading everything into RAM.

Use streaming.

Chunk processing.

Incremental writing.

Disk-based temporary files.

---

# Performance

Pipeline should process independent segments concurrently.

Use configurable worker pool.

Avoid memory explosion.

Use async wherever possible.

Limit FFmpeg threads.

Reuse resources.

---

# Render Free Compatibility

Everything must run on Render Free.

No GPU dependency.

No paid API dependency.

No premium services required.

Optional engines remain optional.

---

# Upload

Large uploads

Resume-safe

Validation

Cleanup

Automatic expiration

---

# Logging

Structured logging.

Every stage logged.

Every failure logged.

Every retry logged.

Every fallback logged.

Every FFmpeg command logged.

---

# Error Handling

User-friendly errors.

Internal detailed logs.

Retry transient failures.

Graceful failure.

Never crash FastAPI.

---

# Health API

Health endpoint

Engine endpoint

Version endpoint

Pipeline diagnostics

---

# Future Premium Ready

Architecture must support later addition of

Lip Sync

Voice Cloning

Speaker Diarization

Multi Speaker Dubbing

Emotion Transfer

Voice Conversion

AI Translation

Automatic Speaker Detection

Real Dialogue Isolation

Music Stem Separation

Streaming TTS

Without changing architecture.

---

# Current Bugs That MUST Be Fixed

Fix gTTS voice selection issue.

Fix Edge TTS compatibility issues.

Fix 403 handling.

Improve retry logic.

Fix overlapping speech.

Improve audio timing.

Improve synchronization.

Improve FFmpeg robustness.

Improve temporary file cleanup.

Improve error reporting.

---

# Code Quality

100% production quality.

No placeholders.

No TODOs.

No duplicate logic.

No dead code.

PEP8 compliant.

Type hints everywhere.

Complete documentation.

---

# Testing

Verify

All imports

All endpoints

All engines

Fallback chain

FFmpeg

FFprobe

Pipeline

Audio merge

Video merge

Subtitle generation

Translation

Long video

Health APIs

Render deployment

Complete end-to-end verification before final delivery.

---

# Deliverables

Complete rewritten files only.

No patches.

No snippets.

No partial implementations.

Every modified file must be provided in full.

Every change must be verified before completion.

Final delivery must include

- Updated source code
- Updated requirements
- Updated documentation
- Updated migration notes
- Verification report

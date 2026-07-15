# API_SPECIFICATION.md

# AI Video Dubbing Platform V3.1 LTS

---

# Overview

This document defines every public API exposed by the AI Video Dubbing Platform.

Goals

- Stable APIs
- Backward Compatibility
- Version Ready
- Production Ready
- REST Architecture
- Async Processing

Base URL

```
https://your-domain.com
```

Future

```
https://your-domain.com/api/v2
```

---

# Authentication

Current Version

No authentication required.

Future

- JWT
- API Keys
- OAuth
- User Accounts
- Rate Limiting

---

# Response Format

Every endpoint returns JSON.

Success

```json
{
    "success": true,
    "data": {}
}
```

Failure

```json
{
    "success": false,
    "error": {
        "code": "ERROR_CODE",
        "message": "Human readable message"
    }
}
```

---

# Health

GET

```
/health
```

Response

```json
{
    "status":"ok"
}
```

Purpose

- Render Health Check
- Monitoring
- Deployment Validation

---

# Root

GET

```
/
```

Returns

- Platform information
- Version
- Available endpoints

---

# Supported Languages

GET

```
/languages
```

Response

```json
{
  "languages": {},
  "count": 41
}
```

---

# TTS Engines

GET

```
/tts/engines
```

Returns

- Registered Engines

Each engine reports

- Name
- Availability
- Health
- Default
- Fallback Rank
- Voice Selection
- Voice Cloning
- Streaming
- Multi Speaker

Example

```json
{
  "default_engine":"gtts"
}
```

---

# Create Dubbing Task

POST

```
/dub
```

Multipart Form

Video File

Required

Target Language

Required

Optional

Source Language

Voice

TTS Engine

Burn Subtitles

Output Format

Example

```
video=file.mp4

target_language=hi

voice=hi-IN-SwaraNeural

tts_engine=edge
```

Response

```json
{
    "task_id":"abc123"
}
```

---

# Task Status

GET

```
/tasks/{task_id}
```

Returns

- Status
- Stage
- Progress
- Voice
- Engine
- Source Language
- Target Language
- Download URL
- Error

---

# Download Video

GET

```
/download/{task_id}
```

Returns

Final dubbed video.

---

# Download Subtitle

GET

```
/download/subtitles/{task_id}
```

Options

Original

Translated

---

# Delete Task

DELETE

```
/tasks/{task_id}
```

Removes

- Metadata
- Temp Files
- Output Files

---

# Pipeline Stages

Possible stages

- Upload
- Validation
- Audio Extraction
- Speech Separation
- Transcription
- Translation
- Subtitle Generation
- TTS Generation
- Audio Enhancement
- Audio Mixing
- Video Merge
- Finalizing
- Completed
- Failed

---

# Supported TTS Engines

Current

- gTTS
- Edge
- Azure
- Piper
- XTTS
- ElevenLabs

Future

- OpenAI
- Fish Speech
- Kokoro
- MeloTTS
- StyleTTS2
- CosyVoice
- F5-TTS

---

# Error Codes

Examples

```
INVALID_VIDEO

INVALID_LANGUAGE

INVALID_ENGINE

FILE_TOO_LARGE

TRANSCRIPTION_FAILED

TRANSLATION_FAILED

TTS_FAILED

AUDIO_MIX_FAILED

VIDEO_MERGE_FAILED

DOWNLOAD_NOT_READY

TASK_NOT_FOUND

TIMEOUT

UNKNOWN_ERROR
```

---

# Progress Values

0%

Upload

10%

Validation

20%

Extraction

35%

Transcription

50%

Translation

65%

Subtitle

75%

TTS

85%

Audio Processing

95%

Final Render

100%

Completed

---

# Future Endpoints

Speaker Detection

```
POST /speaker-diarization
```

Voice Cloning

```
POST /voice-clone
```

Lip Sync

```
POST /lip-sync
```

Resume Task

```
POST /tasks/{id}/resume
```

Cancel Task

```
POST /tasks/{id}/cancel
```

Logs

```
GET /tasks/{id}/logs
```

Statistics

```
GET /stats
```

Queue

```
GET /queue
```

Cache

```
GET /cache
```

Metrics

```
GET /metrics
```

---

# API Stability Rules

Never remove endpoints.

Never rename endpoints.

Never break request schema.

Never break response schema.

Only add optional fields.

Maintain backward compatibility.

---

# Versioning Policy

Current

```
v1
```

Future

```
v2
```

```
v3
```

Older versions remain supported until officially deprecated.

---

# Production Rules

Every endpoint must

- Validate inputs
- Return structured errors
- Log requests
- Log failures
- Support async execution
- Support retries where applicable
- Be fully documented
- Remain backward compatible

End of Document

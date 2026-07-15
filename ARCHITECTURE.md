# ARCHITECTURE.md

# AI Video Dubbing Platform V3.1 LTS

## Production Architecture

Version: 3.1 LTS

Status: Production

---

# PURPOSE

This document defines the complete architecture of the AI Video Dubbing Platform.

Every implementation must follow this architecture.

No module should violate this design.

---

# DESIGN GOALS

Primary goals:

- Production Ready
- Modular
- Maintainable
- Extensible
- Render Free Compatible
- Multi Engine
- Future Proof
- High Performance
- Fault Tolerant

---

# HIGH LEVEL PIPELINE

Video Upload

↓

Validation

↓

Metadata Extraction

↓

Audio Extraction

↓

Source Separation (Optional)

↓

Speech Detection (VAD)

↓

Transcription

↓

Translation

↓

Subtitle Generation

↓

Sentence Alignment

↓

Voice Planning

↓

TTS Generation

↓

Audio Enhancement

↓

Voice Alignment

↓

Dub Audio Assembly

↓

Original Audio Analysis

↓

Background Music Preservation

↓

SFX Preservation

↓

Final Audio Mix

↓

Lip Sync Preparation

↓

Video Merge

↓

Quality Verification

↓

Output Generation

↓

Cleanup

---

# CORE MODULES

app.py

↓

API Layer

↓

Pipeline Controller

↓

Service Layer

↓

Engine Layer

↓

Utilities

↓

Storage Layer

---

# API LAYER

Responsibilities

- Upload API

- Status API

- Download API

- Languages API

- Voices API

- Engine API

- Health API

- Metrics API

API Layer never contains business logic.

---

# PIPELINE CONTROLLER

Responsible for:

Stage execution

Progress updates

Retries

Recovery

Task state

Cancellation

Resume support

---

# SERVICE LAYER

Contains:

Audio Extractor

Audio Cleaner

Subtitle Service

Translation Service

Transcription Service

TTS Service

Video Merger

Audio Mixer

Voice Isolation

Quality Analyzer

---

# ENGINE LAYER

Registered engines only.

Current

gTTS

Edge

Azure

Piper

XTTS

ElevenLabs

Future

OpenAI TTS

Fish Speech

Kokoro

StyleTTS2

F5-TTS

CosyVoice

Dia

Parler TTS

MeloTTS

SparkTTS

Each engine must implement BaseTTSEngine.

---

# ENGINE MANAGER

Responsibilities

Lazy initialization

Health checks

Capability detection

Fallback chain

Caching

Retry

Logging

Metrics

Engine selection

---

# STORAGE

Temporary

uploads/

processing/

segments/

cache/

outputs/

logs/

Permanent

Future

Object Storage

S3

Cloudflare R2

Backblaze

---

# CONFIGURATION

Every configurable value belongs only in config.py

Never hardcode.

Examples

Timeout

Codec

Sample Rate

Threads

Engine Order

Retry Count

Voice Defaults

Language Mapping

Upload Limits

# AUDIO PIPELINE

Video

↓

Extract Audio

↓

Normalize

↓

Noise Analysis

↓

Speech Detection

↓

Speaker Detection (Future)

↓

Source Separation

↓

Speech Track

↓

Background Track

↓

Music Track

↓

Effects Track

↓

Voice Dubbing

↓

Dynamic Mixing

↓

Limiter

↓

Loudness Normalization

↓

AAC Encoding

---

# VIDEO PIPELINE

Input Video

↓

Validation

↓

Metadata

↓

Frame Analysis

↓

Silent Copy

↓

Audio Merge

↓

Subtitle Embed

↓

Final MP4

---

# TRANSLATION PIPELINE

Whisper

↓

Segments

↓

Language Detection

↓

Translation

↓

Sentence Cleanup

↓

Context Correction

↓

Subtitle Builder

↓

Voice Builder

---

# AUDIO ENHANCEMENT

Every generated voice passes through

Silence Trimming

↓

Fade In

↓

Fade Out

↓

Peak Limiter

↓

Compression

↓

LUFS Normalization

↓

EQ

↓

Final Encode

---

# MIXING

Never replace entire original audio.

Instead

Original Audio

↓

Voice Removal

↓

Keep Music

↓

Keep Ambience

↓

Keep Effects

↓

Add Dub Voice

↓

Automatic Ducking

↓

Limiter

↓

Final Mix

---

# VOICE ISOLATION ARCHITECTURE

Goal:

Preserve the original background music and sound effects while replacing
only spoken dialogue.

Pipeline

Original Audio

↓

Voice Detection

↓

Speech Segmentation

↓

Voice Isolation

↓

Background Separation

↓

Dub Voice Generation

↓

Dynamic Mixing

↓

Final Audio

If AI source separation is unavailable (Render Free mode):

- Preserve original audio
- Lower original audio automatically during speech
- Restore original volume after speech
- Never mute the entire soundtrack

Future optional engines:

- Demucs
- UVR
- MDX-Net

These are optional and must never be required for deployment.

---

# BACKGROUND MUSIC PRESERVATION

Background music should remain unchanged whenever possible.

Rules

- Never completely remove music.
- Never replace music.
- Never regenerate music.
- Keep ambience.
- Keep environmental sounds.
- Keep crowd noise.
- Keep cinematic effects.

If source separation is unavailable:

Apply automatic ducking only during synthesized speech.

---

# SFX PRESERVATION

Always preserve:

Door sounds

Footsteps

Rain

Wind

Animals

Traffic

Room ambience

Weapon sounds

Explosion effects

Game sounds

Notification sounds

Environmental sounds

Only dialogue should change.

---

# AUDIO MIXER

The Audio Mixer is responsible for combining:

Original Background

+

Original Music

+

Original SFX

+

Dub Voice

↓

Limiter

↓

Loudness Normalization

↓

Final AAC Audio

Responsibilities

Automatic Gain

Automatic Ducking

Peak Limiting

Clipping Prevention

Loudness Target

Silence Cleanup

Sample Rate Conversion

Channel Matching

---

# AUDIO QUALITY TARGETS

Output Codec

AAC

Bitrate

192 kbps

Sample Rate

48000 Hz

Channels

Stereo

Target Loudness

-16 LUFS

Peak

-1 dBTP

---

# VOICE QUALITY PIPELINE

Every generated voice passes through

Trim Leading Silence

↓

Trim Ending Silence

↓

Fade In

↓

Fade Out

↓

Noise Gate

↓

EQ

↓

Compression

↓

Limiter

↓

LUFS Normalize

↓

Final Encode

---

# TIMING ALIGNMENT

Every subtitle segment keeps:

Start Time

End Time

Duration

Speech Rate

Pause Duration

The synthesized voice should respect the original timing.

If speech exceeds the slot:

Increase speech rate gradually.

If still longer:

Split sentence.

Never overlap into the next segment.

---

# OVERLAP PREVENTION

Voice overlap is forbidden.

Before assembling audio:

Validate

Current End Time

<

Next Start Time

If overlap exists:

Option 1

Trim silence.

Option 2

Increase speaking rate slightly.

Option 3

Reduce pause duration.

Option 4

Split sentence.

Never allow overlapping voices.

---

# LONG VIDEO SUPPORT

Target

2 Hours

Processing Method

Chunk Based

Recommended Chunk Size

5 Minutes

Pipeline

Video

↓

Chunk Split

↓

Independent Processing

↓

Merge Results

↓

Final Output

Benefits

Lower RAM usage

Recovery support

Restart from failed chunk

Better Render compatibility

---

# CHUNK PROCESSING

Every chunk has:

Own subtitles

Own transcription

Own translation

Own TTS

Own temporary files

After completion:

Chunks merge automatically.

---

# MEMORY OPTIMIZATION

Never load entire video into memory.

Always stream.

Always process incrementally.

Delete temporary chunk files after successful merge.

Keep only:

Final output

Logs

Metadata

---

# CPU OPTIMIZATION

Parallelize where possible.

Allowed

Translation

Subtitle generation

TTS generation

FFmpeg processing

Forbidden

Shared mutable state.

---

# RENDER FREE COMPATIBILITY

Must work within Render Free limitations.

Rules

No GPU requirement.

No CUDA dependency.

No PyTorch unless optional.

No mandatory large AI models.

Memory efficient.

Startup under platform limits.

Gracefully disable unavailable optional features.

---

# OPTIONAL FEATURES

Optional features must automatically disable themselves if dependencies
are unavailable.

Never crash the application.

Instead

Log warning

Continue pipeline

Mark capability unavailable

---

# FAULT TOLERANCE

Every stage must support:

Retry

Recovery

Graceful failure

Clear error message

Detailed logging

No silent failures.

---

# LOGGING STANDARD

Every stage logs

Start

Finish

Duration

Warnings

Retries

Errors

Final Result

Each log entry should include

Task ID

Stage

Engine

Execution Time

---

# LIP SYNC ARCHITECTURE

Status

Future Ready

Default

Disabled

Goal

Synchronize synthesized speech with the speaker's mouth movement while
keeping the architecture modular.

Supported Providers (Future)

- Wav2Lip
- MuseTalk
- SadTalker
- VideoReTalking
- LatentSync
- LivePortrait

Rules

Lip-sync must be optional.

If the dependency is unavailable:

- Skip lip-sync.
- Continue normal dubbing.
- Never fail the pipeline.

Pipeline

Dubbed Audio

↓

Lip Sync Engine

↓

Synced Frames

↓

Video Encoder

↓

Final Video

---

# MULTI-SPEAKER ARCHITECTURE

Future Ready

Pipeline

Speech Segments

↓

Speaker Diarization

↓

Speaker Identification

↓

Voice Assignment

↓

Independent TTS

↓

Audio Merge

↓

Final Mix

Capabilities

Multiple speakers

Different voices

Gender-specific voices

Speaker memory

Per-speaker configuration

---

# VOICE CLONING ARCHITECTURE

Status

Optional

Supported Future Engines

XTTS

ElevenLabs

OpenVoice

Fish Speech

CosyVoice

Rules

Voice cloning must never be mandatory.

If unavailable:

Use default language voice.

Never fail the pipeline.

---

# PERFORMANCE OPTIMIZATION

Goals

Fast startup

Low memory

High stability

Rules

Lazy loading

Lazy initialization

Streaming I/O

Chunk processing

Reusable FFmpeg commands

Shared HTTP sessions

Connection pooling

Automatic cleanup

---

# PARALLEL EXECUTION

Allowed

Subtitle generation

Translation

TTS generation

File validation

Metadata extraction

Health checks

Not Allowed

Shared mutable state

Race conditions

Unsafe global variables

---

# QUEUE ARCHITECTURE

Current

In-process queue

Future

Redis Queue

RabbitMQ

Celery

Cloud Tasks

Queue interface must remain abstract.

Pipeline code must not depend on queue implementation.

---

# STORAGE ARCHITECTURE

Current

Local Storage

Future

AWS S3

Cloudflare R2

Backblaze B2

Google Cloud Storage

Azure Blob Storage

Storage provider must be replaceable through configuration only.

---

# CACHE ARCHITECTURE

Current

Memory Cache

Future

Redis

Disk Cache

Object Storage Cache

Cached Items

Generated speech

Translations

Subtitle files

Metadata

Voice models

---

# MONITORING

Expose metrics for

Pipeline duration

Average processing time

Engine usage

Engine failures

Retry count

Memory usage

CPU usage

Queue size

Completed tasks

Failed tasks

Cancelled tasks

---

# SECURITY

Validate every upload.

Reject unsupported files.

Sanitize filenames.

Prevent path traversal.

Limit upload size.

Never expose API keys.

Never expose internal filesystem paths.

Never log secrets.

---

# TESTING STRATEGY

Every module should support

Unit Testing

Integration Testing

End-to-End Testing

Regression Testing

Performance Testing

Failure Recovery Testing

Fallback Testing

---

# CODE QUALITY

Mandatory

Type hints

Docstrings

Logging

No dead code

No duplicate logic

No circular imports

No wildcard imports

No hidden side effects

Production-ready implementations only

---

# DOCUMENTATION

Every implementation must update

PROJECT_SPECIFICATION.md

IMPLEMENTATION_RULES.md

ARCHITECTURE.md

ROADMAP.md

CHANGELOG.md

Migration documentation

API documentation

---

# DEPLOYMENT TARGETS

Current

Render Free

Future

Render Paid

Railway

Fly.io

Google Cloud Run

AWS ECS

Azure App Service

Docker

Kubernetes

Deployment-specific code must remain isolated.

---

# DESIGN PRINCIPLES

The platform must always prioritize

1. Correctness over speed

2. Reliability over complexity

3. Maintainability over cleverness

4. Modularity over monolithic design

5. Configuration over hardcoding

6. Graceful degradation over crashes

7. Production quality over prototypes

8. Extensibility over rewrites

9. User experience over implementation convenience

10. Future compatibility over short-term optimization

---

# FINAL ARCHITECTURE REQUIREMENT

Any new feature added to the platform must:

- Integrate into the existing architecture.
- Respect all implementation rules.
- Be configurable.
- Be documented.
- Be testable.
- Support graceful failure.
- Remain Render Free compatible unless explicitly marked as an optional premium feature.

This architecture document is the authoritative blueprint for the AI Video Dubbing Platform V3.1 LTS.

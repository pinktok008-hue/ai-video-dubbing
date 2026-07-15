# CLAUDE.md

# AI Video Dubbing Platform V3.1 LTS

## Permanent Development Instructions

This document defines the permanent development rules for the entire repository.

These instructions are permanent and apply to every future implementation, refactor, migration, optimization, bug fix, feature addition, and code review.

Unless explicitly instructed otherwise, these rules always take priority.

---

# PROJECT OBJECTIVE

Build and maintain a production-grade AI Video Dubbing Platform that is:

- Stable
- Reliable
- Modular
- Maintainable
- Extensible
- Backward Compatible
- Render Free Compatible
- Production Ready

Primary goals:

1. Reliability
2. Audio Quality
3. Video Quality
4. Performance
5. Scalability
6. Developer Experience
7. Future Expandability

---

# DEVELOPMENT PRINCIPLES

Always prefer

- Clean Architecture
- SOLID Principles
- DRY
- KISS
- Dependency Injection
- Composition over Inheritance
- Async Programming
- Config Driven Development

Never sacrifice maintainability for short-term convenience.

---

# BEFORE WRITING CODE

Never immediately begin implementation.

Always perform:

1. Architecture Audit
2. Dependency Audit
3. Import Audit
4. Circular Dependency Check
5. Existing Feature Audit
6. Impact Analysis
7. Migration Plan
8. Rollback Strategy
9. Verification Plan

Only after these steps begin implementation.

---

# IMPLEMENTATION RULES

Never generate

- Placeholder code
- TODO implementations
- Pseudo code
- Mock production logic
- Temporary hacks

Always produce

- Complete files
- Production-ready implementations
- Fully typed code
- Complete documentation
- Working implementations

Whenever a file changes:

Rewrite the entire file.

Never provide partial patches unless explicitly requested.

---

# BACKWARD COMPATIBILITY

Never break existing APIs.

Never remove existing endpoints.

Never rename public APIs.

Never silently change behavior.

Always provide migration compatibility.

Older clients should continue working whenever technically possible.

---

# CONFIGURATION RULES

Never hardcode:

- API Keys
- URLs
- Paths
- Timeouts
- Retry Counts
- Voice Names
- Engine Names
- Sample Rates
- Bitrates
- Thread Counts
- Cache Sizes
- Audio Parameters
- FFmpeg Commands

Everything configurable belongs inside:

config.py

or

Settings

---

# PYTHON STANDARDS

Target Version

Python 3.12

Requirements

- Full Type Hints
- Dataclasses where appropriate
- Async/Await
- pathlib
- Context Managers
- Exception Chaining
- Logging
- Structured Errors

Avoid

- Global mutable state
- Wildcard imports
- Circular imports
- Duplicate logic

---

# PROJECT ARCHITECTURE

The project must remain modular.

Presentation Layer

↓

API Layer

↓

Pipeline Layer

↓

Services

↓

Engine Managers

↓

Concrete Engines

↓

External Services

Every module must have one responsibility.

---

# TTS ARCHITECTURE

Supported engines

- gTTS
- Edge TTS
- Azure Speech
- Piper
- XTTS
- ElevenLabs

Future engines

- OpenAI TTS
- Fish Speech
- Kokoro
- StyleTTS2
- MeloTTS
- F5-TTS
- CosyVoice

Every engine must implement

BaseTTSEngine

Engine selection must always happen through

TTSEngineManager

No engine-specific logic may exist inside

pipeline.py

or

tts_service.py

Engine-specific behavior belongs only inside the engine implementation.

---

# ENGINE MANAGER RULES

TTSEngineManager is responsible for

- Engine Selection
- Health Checks
- Initialization
- Retry
- Timeout Handling
- Automatic Fallback
- Voice Compatibility
- Request Adaptation
- Cache Integration
- Logging

No other module should duplicate this logic.

---

# FALLBACK RULES

If selected engine fails

↓

Retry

↓

If still fails

↓

Use next configured fallback

↓

Continue until success

↓

If every engine fails

↓

Return one combined error containing every engine failure.

Never stop after the first failure.

Fallback order must remain configurable.

---

# ENGINE REQUIREMENTS

Every engine should support whenever technically possible

- Retry
- Timeout
- Health Check
- Capability Discovery
- Voice Selection
- Streaming
- Voice Cloning (optional)
- Multi Speaker (optional)
- Language Validation
- Structured Errors

Optional capabilities must gracefully degrade.

The pipeline must never crash simply because an optional capability is unavailable.

---

# CHANGELOG

All notable changes to this project will be documented in this file.

This project follows semantic versioning where practical.

---

# [3.2.0] - Planned

## Major Architecture

- Complete production-grade modular TTS architecture.
- Multiple TTS engine support.
- Automatic fallback engine manager.
- Engine capability detection.
- Health check system.
- Voice cache.
- Config-driven engine registry.

---

## Audio Pipeline

Added:

- Audio Enhancement Pipeline
- Silence Trimming
- Loudness Normalization
- Dynamic Compression
- Equalizer
- Peak Limiter
- Noise Gate
- Audio Fade In
- Audio Fade Out
- Volume Matching

---

## Speech Processing

Added:

- Voice Timeline Alignment
- Overlap Prevention
- Segment Validation
- Audio Duration Validation
- Segment Recovery
- Timeline Repair

---

## Background Audio

Added:

- Preserve Original Background Music
- Preserve Original SFX
- Voice Ducking
- Automatic Audio Mixing

When source separation is unavailable:

- Keep original audio
- Reduce original volume only while dubbed speech plays
- Restore original volume after speech

---

## Long Video Processing

Added:

- Chunk Processing
- Resume Processing
- Chunk Merge
- Temporary Cleanup
- Memory Optimization
- Streaming File Processing

Target Support:

- Up to 2 Hour Videos

---

## Performance

Added:

- Parallel Translation
- Parallel TTS
- Optimized FFmpeg Commands
- Async File Processing
- Shared HTTP Sessions
- Lazy Loading
- Voice Cache

---

## Render Free Compatibility

Supported:

- FastAPI
- Python 3.12
- FFmpeg
- Whisper API
- Deep Translator
- gTTS
- Edge TTS

Optional:

- Azure
- Piper
- XTTS
- ElevenLabs

Unavailable optional engines never stop the pipeline.

---

## API

Added:

- Engine Health Endpoint
- Engine Capability Endpoint
- Voice Listing Endpoint
- Better Error Responses
- Structured Logs

---

## Reliability

Improved:

- Retry Logic
- Timeout Handling
- Engine Recovery
- Automatic Fallback
- Detailed Error Reporting
- Validation

---

## Documentation

Added:

- PROJECT_SPECIFICATION.md
- IMPLEMENTATION_RULES.md
- ARCHITECTURE.md
- ROADMAP.md
- CLAUDE.md

---

## Future Ready

Architecture prepared for:

- Lip Sync
- Voice Cloning
- Speaker Diarization
- Multi Speaker
- Streaming TTS
- Voice Conversion
- API Versioning

These features remain disabled unless free dependencies are available.

---

# [3.1.0]

Initial modular multi-engine TTS architecture.

- Engine Manager
- BaseTTSEngine
- gTTS
- Edge
- Azure
- Piper
- XTTS
- ElevenLabs
- Health Checks
- Fallback System

---

# [3.0.0]

Original AI Video Dubbing Platform.

Features:

- Upload
- Transcription
- Translation
- Subtitle Generation
- Edge TTS
- Audio Merge
- Final Render

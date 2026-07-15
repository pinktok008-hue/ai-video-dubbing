# CLAUDE.md

# AI Video Dubbing Platform V3.1 LTS

## Permanent Development Instructions

This document defines the permanent development rules for this repository.

Every future implementation must follow these instructions.

---

# PRIMARY OBJECTIVE

Build and maintain a production-grade AI Video Dubbing Platform.

Priorities

1. Stability

2. Reliability

3. Maintainability

4. Modularity

5. Extensibility

6. Backward Compatibility

7. Render Free Compatibility

---

# BEFORE WRITING CODE

Never immediately start coding.

Always perform:

1. Architecture audit

2. Dependency audit

3. Import audit

4. Impact analysis

5. Migration plan

6. Verification plan

Only then begin implementation.

---

# FILE MODIFICATIONS

Never provide partial patches.

Never provide diff-only changes.

Whenever a file changes:

Rewrite the complete file.

Every rewritten file must remain production ready.

---

# BACKWARD COMPATIBILITY

Never break existing APIs.

Never rename public endpoints unless explicitly requested.

Never remove existing functionality without providing a migration path.

---

# CONFIGURATION

Never hardcode

API Keys

Timeouts

Paths

Voice Names

Engine Names

Retry Counts

Bitrates

Sample Rates

Everything configurable belongs in config.py.

---

# TTS ENGINE RULES

Supported engines

- gTTS
- Edge
- Azure
- Piper
- XTTS
- ElevenLabs

Future engines

- OpenAI
- Fish Speech
- Kokoro
- StyleTTS2
- MeloTTS
- F5-TTS
- CosyVoice

Rules

Every engine must implement BaseTTSEngine.

Engine selection must always pass through TTSEngineManager.

No engine-specific logic should exist inside pipeline.py.

---

# FALLBACK RULES

If the selected engine fails

↓

Try next configured engine

↓

Continue until success

↓

If all fail

↓

Return one combined error

Never stop after the first engine failure.

---

# AUDIO QUALITY

Every generated voice should pass through

Silence trimming

Fade in

Fade out

Compression

EQ

Peak limiting

LUFS normalization

Volume matching

Timing alignment

Overlap prevention

---

# AUDIO MIXING

Do not replace the complete original audio.

Goal

Replace only spoken dialogue.

Preserve

Background music

Ambient sounds

Environmental sounds

Sound effects

If source separation is unavailable

Automatically duck the original audio only while dubbed speech plays.

---

# VIDEO PIPELINE

Required stages

Upload

Validation

Audio Extraction

Transcription

Translation

Subtitle Generation

TTS

Audio Enhancement

Audio Mixing

Video Merge

Verification

Cleanup

---

# LONG VIDEO SUPPORT

Target

2 hours

Implementation

Chunk processing

Chunk recovery

Chunk merge

Streaming processing

Temporary cleanup

Memory optimization

---

# OPTIONAL FEATURES

Optional features must automatically disable themselves if dependencies are unavailable.

Never crash the pipeline because an optional feature is unavailable.

Examples

Lip Sync

Voice Cloning

Streaming TTS

Speaker Diarization

---

# PERFORMANCE

Prefer

Lazy loading

Streaming I/O

Parallel processing

Connection pooling

Shared HTTP sessions

Caching

Automatic cleanup

---

# CODE STYLE

Mandatory

Type hints

Docstrings

Structured logging

Meaningful variable names

No duplicated business logic

No dead code

No circular imports

No wildcard imports

---

# DOCUMENTATION

Whenever architecture changes

Update

PROJECT_SPECIFICATION.md

IMPLEMENTATION_RULES.md

ARCHITECTURE.md

ROADMAP.md

CHANGELOG.md

API documentation

Migration documentation

---

# TESTING

Before declaring implementation complete

Verify

Application startup

Imports

Configuration

API endpoints

Upload

Translation

Subtitles

TTS

Fallback chain

Audio merge

Video merge

Cleanup

Render deployment

Health endpoint

---

# CLAIMS

Never claim

"Production Ready"

unless verified.

Never claim

"Fixed"

unless reproduced and verified.

Never invent successful test results.

Report exactly what was verified.

---

# RENDER FREE

Default implementation must work on

Render Free

without requiring

GPU

CUDA

PyTorch

Paid APIs

Premium cloud infrastructure

Heavy models

Optional features may require additional dependencies but must degrade gracefully.

---

# FINAL RULE

Whenever implementing a new feature

Always

Audit

Plan

Implement

Verify

Document

Only then declare the work complete.

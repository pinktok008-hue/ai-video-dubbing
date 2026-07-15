# TESTING_GUIDE.md

# AI Video Dubbing Platform V3.1 LTS

## Purpose

This document defines the complete testing process required before every release.

A feature is not considered complete until it has been verified.

---

# Testing Philosophy

Never assume.

Always verify.

Never claim a feature works unless it has been tested.

Never fake test results.

If something cannot be tested, explicitly document why.

---

# Testing Levels

## 1. Unit Testing

Test every module independently.

Examples:

- File Manager
- Task Manager
- Progress Manager
- Translation Service
- Subtitle Service
- TTS Manager
- Every TTS Engine
- Audio Enhancement
- Audio Mixing
- Video Merger

---

## 2. Integration Testing

Verify the interaction between services.

Examples:

Upload

↓

Extraction

↓

Transcription

↓

Translation

↓

Subtitle

↓

TTS

↓

Enhancement

↓

Mixing

↓

Rendering

---

## 3. End-to-End Testing

Upload a real video.

Verify the complete pipeline.

Ensure downloadable output is produced.

---

## 4. Regression Testing

Every bug fix must include regression testing.

Previously fixed bugs must never reappear.

---

# API Testing

Verify every endpoint.

Examples

GET /

GET /health

GET /languages

GET /tts/engines

POST /dub

GET /tasks/{id}

GET /download/{id}

DELETE /tasks/{id}

Invalid requests must return proper HTTP errors.

---

# Upload Testing

Verify

MP4

MOV

AVI

MKV

WEBM

Different resolutions

Different frame rates

Different durations

Different file sizes

Invalid uploads

Large uploads

Corrupted uploads

---

# Translation Testing

Verify

Short text

Long text

Mixed language

Emoji

Unicode

Special characters

RTL languages

Batch translation

---

# Subtitle Testing

Verify

Timing

Formatting

Encoding

Unicode

Long lines

Short lines

Empty subtitles

---

# TTS Testing

Verify every engine independently.

gTTS

Edge

Azure

Piper

XTTS

ElevenLabs

Verify

Initialization

Voice selection

Retry

Timeout

Fallback

Caching

Parallel synthesis

Audio generation

---

# Audio Enhancement Testing

Verify

Silence trimming

Noise reduction (if enabled)

Compression

EQ

Limiter

Normalization

Fade in

Fade out

Peak control

---

# Audio Mixing Testing

Verify

Original voice removed correctly

Background music preserved

Sound effects preserved

No clipping

No distortion

No echo

No voice overlap

Correct timing

Correct synchronization

---

# Video Rendering Testing

Verify

Audio sync

Subtitle sync

Video duration

Codec compatibility

Output bitrate

Audio bitrate

Frame integrity

Playable output

---

# Long Video Testing

Required durations

5 min

15 min

30 min

60 min

90 min

120 min

Verify

Memory usage

CPU usage

Temporary storage

Chunk recovery

Resume capability

Pipeline stability

---

# Performance Testing

Measure

Processing speed

Memory usage

Disk usage

FFmpeg performance

Translation speed

TTS speed

Rendering speed

Parallel execution

---

# Failure Testing

Simulate

Network loss

Engine failure

Timeout

Disk full

Invalid input

Corrupted media

Missing dependency

Missing API key

Verify graceful failure.

---

# Render Free Testing

Verify deployment on Render Free.

Confirm

No GPU required

Memory stays within limits

CPU usage acceptable

Application starts successfully

Health endpoint responds

Uploads work

Downloads work

Cleanup executes

---

# Security Testing

Verify

Path traversal prevention

Invalid filenames

Large upload limits

Temporary file cleanup

Input validation

Safe subprocess execution

---

# Logging Verification

Verify logs contain

Task ID

Stage

Duration

Warnings

Errors

Fallback engine

Recovery actions

No secrets

No API keys

---

# Acceptance Criteria

A release is considered complete only if

✓ All APIs work

✓ Pipeline completes successfully

✓ Output video is playable

✓ Audio is synchronized

✓ Subtitles are synchronized

✓ No crashes

✓ No data corruption

✓ Documentation updated

✓ Changelog updated

✓ Manual verification completed

---

# Future Testing

Future features must include testing before release.

Examples

Lip Sync

Voice Cloning

Streaming TTS

Speaker Diarization

Multi-speaker dubbing

Automatic speaker detection

Any new engine

No feature may bypass the testing process.

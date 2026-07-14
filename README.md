# 🎬 AI Video Dubbing Platform V3.1 LTS

A production-ready AI-powered video dubbing backend built with FastAPI.

## ✨ Features

- 🎤 Groq Whisper Speech-to-Text
- 🌍 Multi-language Translation
- 🔊 Modular Multi-Engine Text-to-Speech
- 🎵 FFmpeg Audio Processing
- 🎬 Automatic Video Dubbing
- ⚡ Async FastAPI Backend
- ☁️ Render Free Compatible

---

# Supported TTS Engines

- ✅ gTTS (Default)
- ✅ Edge TTS
- ✅ Azure Speech
- ✅ Piper
- ✅ XTTS
- ✅ ElevenLabs

Features:

- Configurable Default Engine
- Configurable Fallback Chain
- Health Checks
- Engine Registry
- Async Processing
- Future Voice Cloning Ready
- Future Multi-Speaker Ready
- Future Lip-Sync Ready

---

# Tech Stack

- Python 3.11+
- FastAPI
- Groq Whisper
- deep-translator
- FFmpeg
- gTTS
- Edge TTS
- Azure Speech SDK

---

# Project Structure

backend_v3/

├── app.py

├── config.py

├── requirements.txt

├── services/

├── models/

├── core/

└── Dockerfile

---

# Installation

```bash
git clone <YOUR_REPOSITORY_URL>

cd backend_v3

pip install -r requirements.txt
```

---

# Run

```bash
uvicorn app:app --reload
```

Open:

```
http://localhost:8000/docs
```

---

# Deployment

Supported:

- Render
- Docker
- Local Linux
- Local Windows

---

# Environment Variables

Copy

```
.env.example
```

to

```
.env
```

Then update your API keys.

---

# Current Version

AI Video Dubbing Platform

Version: **V3.1 LTS**

Status:

✅ Production Ready

---

# Roadmap

## V3.2

- Speaker Diarization
- Multi-Speaker Dubbing
- Voice Cloning
- Lip Sync
- Background Queue
- Audio Cache

---

# License

Private Repository

Copyright © 2026

All Rights Reserved.

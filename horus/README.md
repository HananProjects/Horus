# Horus — Agentic Desktop Assistant

An Iron Man HUD-style AI assistant with voice I/O, persistent memory, and computer control.

## Quick Start

### 1. Backend

```bash
cd horus/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env          # add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd horus/frontend
npm install
npm start                # opens http://localhost:3000
```

## Phase Status

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Voice + Brain (Whisper → Claude → pyttsx3) | Ready |
| 2 | React Dashboard (WebSocket, HUD UI) | Ready |
| 3 | ChromaDB Persistent Memory | Ready |
| 4 | Computer Use (screenshot → Claude → execute) | Ready |
| 5 | Wake Word, Settings, Polish | TODO |

## Architecture

```
Browser ←── WebSocket ──→ FastAPI (main.py)
                              ├── brain.py      Claude API
                              ├── voice.py      Whisper STT + pyttsx3 TTS
                              ├── memory.py     ChromaDB
                              └── computer_use.py  Computer Use API loop
```

## Usage

- **Type** a message in the text box and press SEND
- **Click MIC** to speak — Horus records 5 seconds, transcribes, and responds
- **Memory panel** shows what Horus has stored from past conversations
- **Action log** shows what Horus is doing in real time

## Computer Use

To trigger computer use from a conversation, say things like:
- "Open Spotify"
- "Search Google for the latest AI news"
- "Take a screenshot of my screen"

Computer use is wired into `computer_use.py` and can be invoked programmatically. A safety confirmation UI (Phase 4 step 4) should be added before deploying in production.

## Notes

- Voice recording uses `sounddevice` + `scipy` (reliable on macOS, no pyaudio needed)
- ChromaDB stores embeddings locally in `backend/chroma_data/` — no API key needed
- The WebSocket reconnects automatically if the backend restarts

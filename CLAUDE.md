# Horus — CLAUDE.md

## Mandatory Update Protocol

> **After every request, always:**
> 1. Update this `CLAUDE.md` with any new context, changes made, decisions taken, or current project state.
> 2. Update the Obsidian vault note at `B:\Obsidian Vault\Projects\Horus.md` to reflect the latest state.
> 3. Append an entry to `B:\Obsidian Vault\log.md` using format: `## [YYYY-MM-DD] project | Horus — description`

---

## Git Branch Workflow

> **Before doing any work on a request:**
> 1. Create a new branch from `main` named after the feature/fix being worked on (e.g. `feature/new-tool`, `fix/voice-bug`, `chore/cleanup`).
> 2. Do all work on that branch — never commit directly to `main`.
> 3. When the work is complete, summarize what the branch contains so it's ready to review and merge.
>
> Branch naming: `feature/<short-name>`, `fix/<short-name>`, or `chore/<short-name>`.

---

## Project Overview

**Horus** is a personal AI desktop assistant with a voice-first sci-fi HUD interface. It runs on Hanan's Windows PC and uses Claude as its reasoning core with 17+ tools including computer control, Gmail, Obsidian vault read/write, and persistent vector memory.

- **Owner:** Hanan (hananqazi21@gmail.com)
- **Location:** `B:\Horus\Horus\`
- **Status:** Active / in development

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Tailwind CSS, THREE.js, globe.gl, WebSocket |
| Backend | FastAPI (Python), Uvicorn |
| AI Brain | Claude Sonnet 4.6 (reasoning + 17 tools) |
| Sub-agents | Claude Haiku (wiki/research tasks) |
| Voice In | OpenAI Whisper (base, offline) |
| Voice Out | pyttsx3 TTS |
| Memory | ChromaDB (persistent vector store) |
| Knowledge | Obsidian vault (B:\Obsidian Vault\) |
| Maps | Google Maps JS API + Geocoding + Directions |
| Email | Gmail API (OAuth 2.0) |

---

## Directory Structure

```
B:\Horus\Horus\
├── horus/
│   ├── backend/
│   │   ├── main.py          ← FastAPI server + WebSocket hub
│   │   ├── brain.py         ← Claude loop + all tools
│   │   ├── agents.py        ← Research / Code / Task sub-agents
│   │   ├── voice.py         ← Whisper STT + pyttsx3 TTS + wake word
│   │   ├── memory.py        ← ChromaDB conversation memory
│   │   ├── obsidian.py      ← Vault indexing + semantic search
│   │   ├── wiki.py          ← LLM wiki synthesis
│   │   ├── gmail.py         ← Gmail read/search/send
│   │   ├── computer_use.py  ← Vision + mouse/keyboard control
│   │   ├── learner.py       ← Autonomous learning daemon (runs every 6h)
│   │   ├── briefing.py      ← Morning briefing generator
│   │   └── self_coder.py    ← Self-improvement code generation
│   └── frontend/
│       └── src/
│           └── components/  ← Dashboard, NeuralSphere, GlobeViewer, etc.
├── scripts/
│   └── start-backend.ps1
├── horus_claude_code_prompt.md   ← Full build prompt / context
├── HORUS_PROJECT_HANDOFF.md      ← Session handoff notes
└── GOOGLE_EARTH_HANDOFF.md       ← Google Earth feature handoff
```

---

## How to Run

```powershell
# Backend
cd B:\Horus\Horus\horus\backend
.\venv\Scripts\uvicorn.exe main:app --reload

# Frontend (separate terminal)
cd B:\Horus\Horus\horus\frontend
npm start
```

---

## Environment Variables (`horus/backend/.env`)

```
ANTHROPIC_API_KEY=...
GOOGLE_MAPS_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

---

## Obsidian Vault Note

`B:\Obsidian Vault\Projects\Horus.md`

Horus also writes autonomous learning logs to `B:\Obsidian Vault\Horus\` every 6 hours.

---

## Recent Changes

<!-- Updated each session — log what changed and when -->

---

## Current State / Notes

<!-- Updated each session — current focus, blockers, next steps -->

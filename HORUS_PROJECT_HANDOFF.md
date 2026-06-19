# Horus — Full Project Handoff

## What Is Horus

Horus is a personal AI assistant with a voice-first sci-fi HUD interface. It runs on Hanan's Windows PC, listens for a wake word, answers questions out loud, controls the computer, manages emails, searches an Obsidian knowledge vault, and autonomously learns and self-improves every 6 hours — even when the app is closed.

**User:** Hanan Hussain — Computer Engineering graduate in Saskatoon, Saskatchewan, Canada. Currently job-hunting for a software engineering role. Uses Windows. Projects tracked in Obsidian vault.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Tailwind CSS, THREE.js, globe.gl, WebSocket |
| Backend | FastAPI (Python), Uvicorn |
| AI | Claude Sonnet 4.6 (brain + agents), Claude Haiku (wiki/research) |
| Voice In | OpenAI Whisper (base model) |
| Voice Out | pyttsx3 (TTS) |
| Memory | ChromaDB (persistent vector store) |
| Knowledge | Obsidian vault (OneDrive synced) |
| Maps | Google Maps JavaScript API + Geocoding API + Directions API |
| Email | Gmail API (OAuth 2.0) |

---

## Directory Structure

```
b:\Horus\Horus\
├── horus/
│   ├── backend/
│   │   ├── main.py               # FastAPI server + WebSocket hub
│   │   ├── brain.py              # Claude loop + all 17 tools
│   │   ├── agents.py             # Research / Code / Task sub-agents
│   │   ├── voice.py              # Whisper STT + pyttsx3 TTS + wake word
│   │   ├── memory.py             # ChromaDB conversation memory
│   │   ├── obsidian.py           # Vault indexing + semantic search
│   │   ├── wiki.py               # LLM wiki synthesis (Karpathy pattern)
│   │   ├── profile.py            # User profile JSON store
│   │   ├── gmail.py              # Gmail read/search/send
│   │   ├── computer_use.py       # Vision + mouse/keyboard control
│   │   ├── learner.py            # Autonomous learning daemon
│   │   ├── briefing.py           # Morning briefing generator
│   │   ├── self_coder.py         # Self-improvement code generation
│   │   ├── nodes.py              # Workspace nodes (JSON store)
│   │   ├── .env                  # API keys (see below)
│   │   ├── credentials.json      # Gmail OAuth credentials
│   │   ├── user_profile.json     # Learned user facts
│   │   └── workspace_nodes.json  # Active workspace nodes
│   │
│   └── frontend/
│       └── src/
│           ├── App.jsx
│           └── components/
│               ├── Dashboard.jsx         # Main HUD layout
│               ├── NeuralSphere.jsx      # 3D THREE.js sphere (the "eye")
│               ├── NodeOrbit.jsx         # Orbital workspace nodes
│               ├── HudPanel.jsx          # Agent + visual panel windows
│               ├── GlobeViewer.jsx       # Google Earth viewer
│               ├── ConversationFeed.jsx  # Message transcript
│               ├── ActionLog.jsx         # Real-time action log
│               ├── MemoryPanel.jsx       # ChromaDB memories viewer
│               ├── SettingsPanel.jsx     # Device + toggles
│               ├── LearningLog.jsx       # Autonomous discoveries toast
│               ├── ConfirmModal.jsx      # Safety gate for computer use
│               ├── StatusBar.jsx         # idle/listening/thinking/speaking
│               └── DraggableWindow.jsx   # Resizable panel primitive
│
├── scripts/
│   └── start-backend.ps1         # Convenience launcher
└── GOOGLE_EARTH_HANDOFF.md       # Google Earth feature detail
```

---

## Environment Variables (`horus/backend/.env`)

```
ANTHROPIC_API_KEY=...        # Claude API (required)
ELEVENLABS_API_KEY=...       # ElevenLabs (present but pyttsx3 is used)
ELEVENLABS_VOICE_ID=...
GOOGLE_MAPS_API_KEY=...      # Google Maps JS + Geocoding + Directions
```

---

## How to Run

```powershell
# Backend
cd horus\backend
.\venv\Scripts\uvicorn.exe main:app --reload
# or:
.\scripts\start-backend.ps1

# Frontend (separate terminal)
cd horus\frontend
npm start
```

Frontend: `http://localhost:3000` — Backend: `http://localhost:8000`

---

## Architecture Overview

```
User (voice or text)
      │
      ▼
[React Frontend]  ──WebSocket──►  [FastAPI main.py]
      ▲                                  │
      │  panels / messages / status      │ trigger detection
      └──────────────────────────────────┤
                                         ├──► brain.py (Claude loop)
                                         │       ├── web_search
                                         │       ├── read/write_file
                                         │       ├── run_command
                                         │       ├── show_visual → panels
                                         │       ├── gmail_*
                                         │       └── delegate_to_agent ──► agents.py
                                         │               (research / code / task)
                                         │
                                         ├──► memory.py (ChromaDB)
                                         ├──► obsidian.py (vault search)
                                         ├──► wiki.py (background synthesis)
                                         ├──► computer_use.py (vision + actions)
                                         ├──► voice.py (STT + TTS + wake word)
                                         └──► learner.py (6-hour background daemon)
```

---

## Backend: main.py

Central hub. Opens a WebSocket at `/ws`. Each message from the frontend is JSON.

**Incoming message types:**
- `text` — User typed a message
- `voice_start` — Record microphone
- `update_settings` — Settings changed
- `clear_memory` — Reset ChromaDB
- `remove_node` — Remove a workspace node
- `node_action` — Action on a node (open, summarize, read_aloud, complete)
- `stop_speaking` — Cancel TTS
- `confirm_response` — User approved/denied a computer-use action

**Outgoing message types:**
- `user_message` — Echo user input
- `assistant_message` — Claude's spoken reply
- `panel` — New visual/agent panel to display
- `action` — Action log entry ("Searching the web…")
- `status` — State change (idle / listening / thinking / speaking)
- `memories` — Full memory list (on connect)
- `nodes` — Workspace node list (on connect + changes)
- `wake_word` — Wake word detected
- `learning_update` — Autonomous discovery from learner
- `error` — Error message

**Trigger detection on user text:**

| Trigger phrases | Handler |
|-----------------|---------|
| "remember that", "don't forget", "keep in mind" | Store explicit memory |
| "open", "click", "type", "search for" | `handle_computer_use()` |
| "save to obsidian", "create a note" | `handle_obsidian_save()` |
| "search my notes", "in my notes" | `handle_obsidian_search()` |
| "good morning horus" | `handle_morning_briefing()` |
| "how does horus", "explain the" | Query graphify knowledge graph |

**Standard conversation flow (`handle_turn`):**
1. Retrieve 3 relevant memories from ChromaDB
2. Search Obsidian vault for related notes
3. Call `brain.chat(user_text, memories, vault_notes)`
4. Display returned panels on frontend
5. Speak response via TTS
6. Store turn in ChromaDB
7. Background: ingest conversation to wiki

**Background loops (started on server startup):**
- `wake_word_loop()` — continuously listens for "horus" wake word
- `learning_loop()` — runs `learner.run_cycle()` every 6 hours
- `_send_startup_brief()` — on WebSocket connect, summarizes what Horus learned while user was away

---

## Backend: brain.py

Single-turn conversation with Claude. Maintains a 40-message rolling history.

**Model:** `claude-sonnet-4-6`
**Max tokens per turn:** 1024

**System prompt tells Claude to:**
- Speak naturally — no markdown, no bullet points (output goes to TTS)
- Use visual tools aggressively (show maps, stocks, images without being asked)
- Call `update_user_profile` whenever anything meaningful is learned about Hanan
- Use `delegate_to_agent` for heavy tasks (runs parallel automatically)
- Have full Gmail access, full file system access
- Summarize learning logs on startup

**17 Tools:**

| Tool | What it does |
|------|-------------|
| `web_search` | DuckDuckGo search, returns 5 results |
| `image_search` | Returns 6 image URLs |
| `read_file` | Read file (max 100KB) |
| `write_file` | Create or overwrite file |
| `list_directory` | List directory contents |
| `run_command` | Execute shell command |
| `open_path` | Launch file/app |
| `add_workspace_node` | Add item to eye (visual workspace) |
| `remove_workspace_node` | Remove workspace node |
| `update_user_profile` | Store learned fact about Hanan |
| `show_visual` | Display a panel (stock/image/video/webpage/score/map) |
| `gmail_search` | Search Gmail (full query syntax) |
| `gmail_read` | Read email by ID |
| `gmail_trash` | Trash specific emails |
| `gmail_bulk_trash` | Trash all emails matching query |
| `gmail_send` | Send/reply to email |
| `delegate_to_agent` | Run research/code/task sub-agent |

**`show_visual` panel types:**

| `content_type` | Data fetched | Display |
|----------------|-------------|---------|
| `stock` | Yahoo Finance (price, 1mo closes) | Sparkline chart |
| `image` | Direct URL | Image with proxy fallback |
| `video` | YouTube embed URL | iframe |
| `webpage` | Any URL | iframe |
| `score` | ESPN API (live poll every 30s) | Team logos, score, status |
| `map` | Google Geocoding → Maps JS | Globe fly-in → street view |

**Tool execution loop:**
1. Call Claude with messages + tools
2. If `stop_reason == "tool_use"`: run tools, loop (max 12 iterations)
3. If `stop_reason == "end_turn"`: done
4. Parallel execution: all `delegate_to_agent` calls run simultaneously via `ThreadPoolExecutor`

---

## Backend: agents.py

Three sub-agents Claude can delegate to. Run in parallel when multiple are called.

| Agent | Model | Tools | Used for |
|-------|-------|-------|---------|
| `research` | Haiku 4.5 | web_search | Current events, fact-finding, prices |
| `code` | Sonnet 4.6 | read_file, write_file, run_command, list_directory | Writing/debugging code |
| `task` | Haiku 4.5 | run_command (PowerShell) | Reminders, scheduling |

---

## Backend: voice.py

**STT:** Whisper base model. Records 5-second chunks from microphone.
**TTS:** pyttsx3 at 185 bpm (adjustable in settings).
**Wake word:** Listens in 2-second bursts. Fuzzy-matches against: horus, horace, horas, harris, hora, horse.

---

## Backend: memory.py

ChromaDB at `./chroma_data/`. Collection: `horus_memory`.

- `store(user_text, assistant_text)` — stores each conversation turn
- `store_fact(fact)` — stores explicit "remember that…" facts
- `retrieve(query, n=3)` — semantic search, injected into each turn
- `get_all()` — for MemoryPanel display
- `clear()` — reset all memories

---

## Backend: obsidian.py

Vault path: `C:\Users\Hanan\OneDrive - University of Saskatchewan\Obsidian Vault`

Indexes all `.md` files into ChromaDB collection `horus_vault`. Searches return notes with L2 distance < 1.3.

Methods: `search(query, n=5)` → list of `{title, path, snippet}`

---

## Backend: wiki.py

After each conversation turn, Claude Haiku updates structured wiki pages in the Obsidian vault (background, doesn't block response). Pages maintained:

- Hanan Profile
- Job Search / Employment Timeline / Companies of Interest
- Interview Prep / Applications Pipeline
- Technical Skills / Personal Life / Goals and Values
- Horus Project / Learning and Growth

---

## Backend: profile.py

JSON store of learned user facts. Categories: preferences, habits, goals, dislikes, projects, facts, communication. Max 30 items per category. Injected into every system prompt.

Seed facts include: Hanan is a Computer Engineering graduate in Saskatoon, job-hunting for SWE roles, building Horus as a portfolio project.

---

## Backend: computer_use.py

Screenshots screen → sends to Claude → Claude returns JSON action → execute via pyautogui. Up to 10 loop iterations. Always requires user confirmation first.

Actions: `open_app`, `click`, `double_click`, `right_click`, `type`, `key`, `scroll`, `done`

---

## Backend: learner.py

Runs every 6 hours. Cycle:
1. Fill wiki knowledge gaps (web search → synthesize)
2. Research proactive topics (Claude releases, job market, AI news)
3. Discover new Claude Code skills on GitHub → auto-install safe ones
4. Propose self-code improvements → apply after safety review

Discoveries sent to frontend as `learning_update` WebSocket messages.

---

## Frontend: Key Components

**NeuralSphere.jsx** — THREE.js scene. 220 nodes on a Fibonacci sphere forming the "eye". Animated particles and data-flow travelers. Glow color changes with state: cyan (idle), amber (thinking), green (speaking).

**HudPanel.jsx** — All floating data panels. Routes `content_type === "map"` to `GlobeViewer`. Handles stock sparklines, ESPN score polling, image proxy, YouTube embeds.

**GlobeViewer.jsx** — Two-phase Google Earth experience:
1. `globe.gl` 3D Earth fly-in from space down to target location (3s)
2. Crossfades to Google Maps JS API at `zoom:17, tilt:45, hybrid` for street-level 3D satellite
- Directions mode: `zoom:10, tilt:0` with `DirectionsService` + `DirectionsRenderer`
- Geocoding via Google Geocoding API (not Nominatim — Nominatim returned wrong countries)
- API key passed directly from backend in panel data (`panel.api_key`)

**NodeOrbit.jsx** — Workspace nodes orbit the eye. Types: pdf, url, image, file, app, task, note, music, search, generic. Click → open/summarize/read_aloud/complete/remove.

**DraggableWindow.jsx** — Primitive used by all panels. Drag header to move, drag edges to resize.

---

## Panel Data Schema

When Claude calls `show_visual`, the backend emits this over WebSocket:

```json
{
  "panel_type": "visual",
  "content_type": "map",
  "title": "Edmonton, Alberta",
  "location": "Edmonton, Alberta",
  "api_key": "AIzaSy...",
  "map_mode": "place",
  "origin": "Saskatoon, SK",
  "destination": "Edmonton, AB",
  "url": "https://www.google.com/maps/embed/v1/..."
}
```

Agent panel:
```json
{
  "panel_type": "research",
  "title": "Latest on Claude 4",
  "content": "Full research text..."
}
```

---

## Google Cloud APIs Enabled

Project: `horus-496801`

- Maps JavaScript API ✅
- Maps Embed API ✅
- Geocoding API ✅ (needed for accurate place → lat/lng)
- Directions API ✅ (needed for route rendering)
- Aerial View API ✅
- Places API ✅
- Roads API ✅
- Routes API ✅
- Street View Static API ✅

Key has no application restrictions (development). Restrict to `localhost:3000` before any deployment.

---

## Git / Branch Info

- Main branch: `master`
- Active feature branch: `googleearth`
- Last commit: `7ab9089` — "Add Google Earth 3D globe viewer with Maps JS street-level fallback"
- Remote: `https://github.com/HananProjects/Horus.git`

---

## Known Issues / Decisions Made

| Issue | Decision |
|-------|---------|
| Nominatim geocoding returned wrong country (Edmonton → Mali) | Switched to Google Geocoding API |
| Maps embed iframe was always 2D flat | Replaced with globe.gl + Maps JS two-phase experience |
| `direction` API key missing from panel data | Backend now sends `api_key`, `map_mode`, `origin`, `destination` in panel data |
| Maps JS script loading race condition with `onload` | Fixed with `callback=__horusMapsReady` parameter |
| `globe.gl` imported at build time causing bundle issues | Dynamically imported inside `useEffect` |

---

## What's Not Done / Next Steps

- Wake word tuning (false positives with pyttsx3 noise)
- ElevenLabs TTS (key is present, pyttsx3 used instead)
- SettingsPanel is partially wired (some toggles don't persist)
- Production security: API key restrictions, HTTPS/WSS, auth
- Error recovery in learner (partial failures silently ignored)
- Computer use on Windows needs full testing (designed for macOS AppleScript in places)
- `briefing.py` calendar uses AppleScript (macOS only) — not functional on Windows

# Horus — Agentic Desktop Assistant

## Project Overview
Build a personal AI assistant called Horus with a React dashboard UI, voice input/output, persistent memory, and the ability to control the user's computer (click, type, navigate). The user is an experienced developer comfortable with Python, React, FastAPI, Docker, and the Claude API.

---

## Tech Stack
- **Backend:** Python, FastAPI, WebSockets
- **Frontend:** React, Tailwind CSS
- **AI Brain:** Anthropic Claude API (`claude-sonnet-4-20250514`)
- **Computer Use:** Anthropic Computer Use API
- **Voice In:** OpenAI Whisper (local, base model)
- **Voice Out:** pyttsx3 (local, free) with option to swap to ElevenLabs
- **Memory:** ChromaDB (local vector database for persistent context)
- **Wake Word:** Porcupine (picovoice free tier)
- **Platform:** macOS

---

## Project Structure
```
horus/
├── backend/
│   ├── main.py              # FastAPI app, WebSocket server
│   ├── brain.py             # Claude API integration
│   ├── computer_use.py      # Screen control via Claude Computer Use API
│   ├── voice.py             # Whisper STT + pyttsx3 TTS
│   ├── memory.py            # ChromaDB persistent memory
│   └── tools.py             # Tool definitions (web search, calendar, etc.)
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Dashboard.jsx       # Main layout
│   │   │   ├── ConversationFeed.jsx # Live transcript
│   │   │   ├── MemoryPanel.jsx     # What Horus remembers
│   │   │   ├── ActionLog.jsx       # What Horus is doing in real time
│   │   │   └── StatusBar.jsx       # Listening / thinking / speaking states
│   └── package.json
├── .env
└── README.md
```

---

## Build Order — Follow This Exactly

### Phase 1 — Voice + Brain (get talking first)
1. Set up FastAPI backend with a `/chat` endpoint
2. Integrate Claude API with a system prompt that gives Horus its personality
3. Integrate Whisper for speech-to-text (record from mic, transcribe, send to Claude)
4. Integrate pyttsx3 for text-to-speech (speak Claude's response back)
5. Test the full loop: speak → transcribe → Claude → speak response

### Phase 2 — React Dashboard
1. Create React app with Tailwind CSS
2. Connect to backend via WebSocket for real-time updates
3. Build ConversationFeed showing user and Horus messages live
4. Build StatusBar showing current state (Listening / Thinking / Speaking / Idle)
5. Build ActionLog showing what Horus is currently doing
6. Dark theme UI — think Iron Man HUD aesthetic (dark background, blue/cyan accents)

### Phase 3 — Persistent Memory
1. Set up ChromaDB locally
2. On every conversation turn, store key facts as embeddings
3. On every new turn, retrieve relevant memories and inject into Claude's context
4. Build MemoryPanel in the dashboard showing stored memories
5. Allow user to say "remember that..." and have it explicitly stored

### Phase 4 — Computer Use (the impressive part)
1. Integrate Anthropic Computer Use API
2. Implement screenshot capture of current screen
3. Allow Claude to request mouse clicks, keyboard input, and scrolling
4. Build safety confirmation UI — show what Horus is about to do and ask for approval before executing
5. Test with simple tasks: "open Spotify", "search Google for X", "take a screenshot"

### Phase 5 — Polish
1. Add wake word detection with Porcupine ("Hey Horus")
2. Add quick action buttons to the dashboard for common tasks
3. Add settings panel (voice speed, model selection, memory management)
4. Add ability to toggle computer use on/off for safety

---

## Horus Personality — System Prompt
```
You are Horus, a highly capable personal AI assistant. You are precise, perceptive, and composed — named after the Egyptian god of the sky and protection, you see everything and act with purpose. You have access to the user's computer, persistent memory of past conversations, and various tools.

When the user asks you to do something on their computer, describe what you are about to do before doing it. Always confirm before taking irreversible actions. Keep responses concise — the user will often be listening rather than reading.

The user's name is Hanan. You know he is a Computer Engineering graduate, currently job hunting in tech, working on personal projects to build his portfolio.
```

---

## Environment Variables (.env)
```
ANTHROPIC_API_KEY=your_key_here
ELEVENLABS_API_KEY=optional
PICOVOICE_API_KEY=optional_for_wake_word
```

---

## Key Technical Notes
- Use WebSockets (not REST) for the frontend↔backend connection so the UI updates in real time as Horus thinks/speaks
- Voice recording should use `sounddevice` + `numpy` on Mac (more reliable than pyaudio on macOS)
- Computer Use API requires taking a screenshot, sending it to Claude, and then executing the returned action — implement this as a loop
- ChromaDB runs fully locally, no API key needed
- All phases should be independently testable — don't couple voice to computer use

---

## Dependencies
```
# Backend
fastapi
uvicorn
websockets
anthropic
openai-whisper
pyttsx3
sounddevice
numpy
chromadb
python-dotenv
pillow          # for screenshots
pyautogui       # for mouse/keyboard control

# Frontend
react
tailwindcss
```

---

## Success Criteria Per Phase
- **Phase 1:** Can have a spoken conversation with Horus
- **Phase 2:** Dashboard shows live conversation and status in real time
- **Phase 3:** Horus remembers things across separate sessions
- **Phase 4:** Horus can open apps, click buttons, and navigate the screen on command
- **Phase 5:** Horus wakes up on voice command and feels polished

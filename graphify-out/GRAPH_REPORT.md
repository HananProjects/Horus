# Graph Report - .  (2026-05-20)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 146 nodes · 172 edges · 16 communities (10 shown, 6 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `791e1353`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 15|Community 15]]

## God Nodes (most connected - your core abstractions)
1. `handle_turn()` - 11 edges
2. `Horus Agentic Desktop Assistant Project` - 10 edges
3. `Dashboard()` - 8 edges
4. `ObsidianVault` - 8 edges
5. `backend/main.py — FastAPI App & WebSocket Server` - 8 edges
6. `Memory` - 7 edges
7. `ComputerUseAgent` - 7 edges
8. `Horus README` - 7 edges
9. `VoicePipeline` - 6 edges
10. `websocket_endpoint()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `backend/computer_use.py — Screen Control` --references--> `pillow`  [INFERRED]
  horus_claude_code_prompt.md → horus/backend/requirements.txt
- `Horus README` --references--> `Phase 5 — Polish`  [EXTRACTED]
  horus/README.md → horus_claude_code_prompt.md
- `sounddevice + numpy Audio Recording` --references--> `scipy`  [INFERRED]
  horus_claude_code_prompt.md → horus/backend/requirements.txt
- `Horus README` --references--> `Horus Agentic Desktop Assistant Project`  [EXTRACTED]
  horus/README.md → horus_claude_code_prompt.md
- `FastAPI Backend` --references--> `fastapi`  [EXTRACTED]
  horus_claude_code_prompt.md → horus/backend/requirements.txt

## Communities (16 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (36): frontend/public/index.html, backend/brain.py — Claude API Integration, ChromaDB Persistent Memory, Anthropic Claude API (claude-sonnet-4-20250514), Anthropic Computer Use API, backend/computer_use.py — Screen Control, ElevenLabs TTS (optional), FastAPI Backend (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (4): Dashboard(), ACTIONS, STATUS_CONFIG, root

### Community 2 - "Community 2"
Cohesion: 0.25
Nodes (15): handle_turn(), is_computer_use_request(), is_obsidian_save_request(), is_obsidian_search_request(), _parse_note_response(), Extract TITLE and BODY from Claude's note-formatting response., send_action(), send_memories() (+7 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (13): browserslist, development, production, dependencies, react, react-dom, react-scripts, name (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.18
Nodes (4): Memory, Explicitly store a user-stated fact., Retrieve the most relevant past memories for a query., Return all stored memories (for the MemoryPanel).

### Community 5 - "Community 5"
Cohesion: 0.22
Nodes (3): ObsidianVault, Keyword search across all vault notes. Returns title, path, snippet, score., Create a new note. Returns the relative path.

### Community 8 - "Community 8"
Cohesion: 0.33
Nodes (6): frontend/components/ActionLog.jsx, frontend/src/App.jsx, frontend/components/ConversationFeed.jsx, frontend/components/Dashboard.jsx, frontend/components/MemoryPanel.jsx, frontend/components/StatusBar.jsx

### Community 10 - "Community 10"
Cohesion: 0.50
Nodes (4): sounddevice + numpy Audio Recording, numpy, scipy, sounddevice

## Knowledge Gaps
- **34 isolated node(s):** `allow`, `name`, `version`, `private`, `react` (+29 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `backend/voice.py — Whisper STT + pyttsx3 TTS` connect `Community 0` to `Community 10`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `backend/main.py — FastAPI App & WebSocket Server` (e.g. with `backend/brain.py — Claude API Integration` and `backend/voice.py — Whisper STT + pyttsx3 TTS`) actually correct?**
  _`backend/main.py — FastAPI App & WebSocket Server` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allow`, `name`, `version` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.09047619047619047 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
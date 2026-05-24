import asyncio
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain import Brain, _open_path, _read_file, _web_search
from voice import VoicePipeline, list_input_devices
from memory import Memory
from computer_use import ComputerUseAgent
from obsidian import ObsidianVault
from wiki import WikiManager
from learner import HorusLearner, LEARNING_INTERVAL_HOURS
from briefing import MorningBriefing
import nodes as node_store

app = FastAPI(title="Horus")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = Brain()
voice = VoicePipeline()
memory = Memory()
computer = ComputerUseAgent()
obsidian = ObsidianVault()
wiki = WikiManager(obsidian)
learner = HorusLearner(wiki, obsidian)
briefer = MorningBriefing(wiki, obsidian)

# Global settings
settings = {
    "computer_use_enabled": True,
    "wake_word_enabled": True,
    "voice_rate": 185,
    "mic_device_index": None,
}

REMEMBER_TRIGGERS = ("remember that", "remember this", "don't forget", "note that", "keep in mind")

COMPUTER_USE_TRIGGERS = (
    "open ", "launch ", "close ", "quit ",
    "search google", "search for ", "go to ", "navigate to ",
    "click on ", "click ", "type ", "scroll ",
    "take a screenshot", "screenshot",
)

OBSIDIAN_SAVE_TRIGGERS = (
    "save to obsidian", "save this to obsidian", "add to obsidian",
    "create a note", "write a note", "make a note",
    "save in obsidian", "put in obsidian", "add this to my notes",
    "note this down", "jot this down",
)

OBSIDIAN_SEARCH_TRIGGERS = (
    "search my notes", "search obsidian", "in my notes",
    "from my notes", "my obsidian", "look in my notes",
    "what do my notes say", "check my notes", "my vault",
)

MORNING_TRIGGERS = (
    "good morning horus",
)

GRAPH_QUERY_TRIGGERS = (
    "how does horus", "how does the", "explain horus", "explain the",
    "what does horus", "where is", "how is horus", "horus architecture",
    "how does brain", "how does memory", "how does voice", "how does obsidian",
    "show me the code", "what functions", "what modules",
)

GRAPH_JSON = "/Users/hanan/Horus/graphify-out/graph.json"
LAST_SEEN_PATH = Path.home() / ".horus_last_seen"
CONVERSATION_TIMEOUT = 8


# ── helpers ────────────────────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()


def is_computer_use_request(text: str) -> bool:
    if not settings["computer_use_enabled"]:
        return False
    lower = text.lower()
    return any(trigger in lower for trigger in COMPUTER_USE_TRIGGERS)


def is_obsidian_save_request(text: str) -> bool:
    return any(t in text.lower() for t in OBSIDIAN_SAVE_TRIGGERS)


def is_obsidian_search_request(text: str) -> bool:
    return any(t in text.lower() for t in OBSIDIAN_SEARCH_TRIGGERS)


def is_morning_briefing_request(text: str) -> bool:
    return any(t in text.lower() for t in MORNING_TRIGGERS)


def is_graph_query(text: str) -> bool:
    return any(t in text.lower() for t in GRAPH_QUERY_TRIGGERS)


def _run_graphify_query(question: str):
    try:
        result = subprocess.run(
            ["graphify", "query", question, "--graph", GRAPH_JSON, "--budget", "1500"],
            capture_output=True, text=True, timeout=20,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _load_last_seen() -> datetime:
    try:
        return datetime.fromtimestamp(float(LAST_SEEN_PATH.read_text().strip()))
    except Exception:
        return datetime.now() - timedelta(hours=24)


def _save_last_seen():
    LAST_SEEN_PATH.write_text(str(datetime.now().timestamp()))


def _parse_note_response(raw: str, fallback_title: str) -> tuple:
    lines = raw.strip().splitlines()
    title = fallback_title[:60]
    body_lines = []
    in_body = False
    for line in lines:
        if line.startswith("TITLE:"):
            title = line.removeprefix("TITLE:").strip()
        elif line.startswith("BODY:"):
            in_body = True
        elif in_body:
            body_lines.append(line)
    body = "\n".join(body_lines).strip() or raw
    return title, body


# ── WebSocket senders ──────────────────────────────────────────────────────

async def send_status(ws: WebSocket, status: str):
    await ws.send_json({"type": "status", "status": status})

async def send_message(ws: WebSocket, role: str, content: str):
    await ws.send_json({"type": "message", "role": role, "content": content})

async def send_action(ws: WebSocket, action: str):
    await ws.send_json({"type": "action", "action": action})

async def send_memories(ws: WebSocket):
    await ws.send_json({"type": "memories", "memories": memory.get_all()})

async def send_nodes(ws: WebSocket):
    await ws.send_json({"type": "nodes", "nodes": node_store.load()})

async def send_settings(ws: WebSocket):
    await ws.send_json({"type": "settings", "settings": settings})

async def send_devices(ws: WebSocket):
    await ws.send_json({"type": "devices", "devices": list_input_devices()})

async def send_obsidian_event(ws: WebSocket, event: str, data: dict):
    await ws.send_json({"type": "obsidian", "event": event, **data})


async def _send_startup_brief(ws: WebSocket, last_seen: datetime):
    """If learning logs exist since last_seen, summarize and send on connect."""
    horus_dir = obsidian.horus_dir
    logs = []
    for path in sorted(horus_dir.glob("Horus Learning Log*.md")):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) > last_seen:
                logs.append(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    if not logs:
        return
    combined = "\n\n---\n\n".join(logs[-5:])
    delta = datetime.now() - last_seen
    away_str = (
        f"{int(delta.total_seconds() // 3600)} hours"
        if delta.total_seconds() >= 3600
        else f"{int(delta.total_seconds() // 60)} minutes"
    )
    summary = await asyncio.to_thread(
        learner._call,
        "You are Horus, giving a concise wake-up brief to Hanan.",
        f"You learned the following while Hanan was away ({away_str}):\n\n{combined}\n\n"
        "Give a 2-3 sentence summary of the most interesting things you discovered. "
        "Be direct and specific. Speak in first person as Horus.",
    )
    if summary:
        await send_message(ws, "assistant", f"**While you were away** ({away_str} ago):\n\n{summary}")


# ── background loops ───────────────────────────────────────────────────────

connected_clients: list[WebSocket] = []
_voice_lock = asyncio.Lock()


async def wake_word_loop():
    while True:
        if not settings["wake_word_enabled"] or not connected_clients:
            await asyncio.sleep(1)
            continue
        detected = await asyncio.to_thread(voice.listen_for_wake_word)
        if detected:
            for ws in connected_clients:
                try:
                    await ws.send_json({"type": "wake_word"})
                except Exception:
                    pass


async def learning_loop():
    # Short delay so the app finishes starting up, then run immediately
    await asyncio.sleep(30)
    while True:
        try:
            discoveries = await learner.run_cycle()
            if discoveries and connected_clients:
                payload = {"type": "learning_update", "discoveries": discoveries}
                for ws in connected_clients:
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(LEARNING_INTERVAL_HOURS * 3600)


@app.on_event("startup")
async def startup():
    asyncio.create_task(wake_word_loop())
    asyncio.create_task(learning_loop())


# ── WebSocket endpoint ─────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)

    confirm_event = asyncio.Event()
    confirm_result = {"approved": False}

    async def request_confirmation(description: str) -> bool:
        confirm_event.clear()
        await ws.send_json({"type": "confirm_action", "description": description})
        await confirm_event.wait()
        return confirm_result["approved"]

    last_seen = _load_last_seen()
    _save_last_seen()

    await send_status(ws, "idle")
    await send_memories(ws)
    await send_settings(ws)
    await send_devices(ws)
    await send_nodes(ws)
    await _send_startup_brief(ws, last_seen)

    current_task = None

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "confirm_response":
                confirm_result["approved"] = data.get("approved", False)
                confirm_event.set()

            elif msg_type == "text":
                voice.interrupt()
                if current_task and not current_task.done():
                    current_task.cancel()
                user_text = data.get("content", "")
                current_task = asyncio.create_task(
                    handle_turn(ws, user_text, request_confirmation)
                )

            elif msg_type == "voice_start":
                voice.interrupt()
                if current_task and not current_task.done():
                    current_task.cancel()
                current_task = asyncio.create_task(
                    handle_voice_turn(ws, request_confirmation)
                )

            elif msg_type == "update_settings":
                new = data.get("settings", {})
                settings.update({k: v for k, v in new.items() if k in settings})
                voice.device_index = settings.get("mic_device_index")
                await send_settings(ws)

            elif msg_type == "clear_memory":
                memory.clear()
                await send_memories(ws)
                await send_message(ws, "assistant", "Memory cleared.")

            elif msg_type == "remove_node":
                node_store.remove(data.get("node_id"))
                await send_nodes(ws)

            elif msg_type == "node_action":
                current_task = asyncio.create_task(
                    handle_node_action(ws, data.get("node_id"), data.get("action"))
                )

            elif msg_type == "stop_speaking":
                voice.stop_speaking()
                await send_status(ws, "idle")
            elif msg_type == "dismiss_panel":
                pass  # frontend handles panel dismissal locally

    except WebSocketDisconnect:
        connected_clients.remove(ws)
        if current_task:
            current_task.cancel()


# ── turn handlers ──────────────────────────────────────────────────────────

async def handle_voice_turn(ws: WebSocket, confirm):
    if _voice_lock.locked():
        return
    async with _voice_lock:
        try:
            await send_status(ws, "listening")
            await send_action(ws, "Recording audio...")
            user_text = await asyncio.to_thread(voice.listen)

            while user_text:
                await send_message(ws, "user", user_text)
                await handle_turn(ws, user_text, confirm)
                await send_status(ws, "listening")
                await send_action(ws, "Listening...")
                user_text = await asyncio.to_thread(voice.listen, CONVERSATION_TIMEOUT)

        except asyncio.CancelledError:
            pass
        finally:
            await send_status(ws, "idle")
            await send_action(ws, "")


async def handle_node_action(ws: WebSocket, node_id: int, action: str):
    all_nodes = node_store.load()
    node = next((n for n in all_nodes if n["id"] == node_id), None)
    if not node:
        await send_message(ws, "assistant", "Node not found.")
        return

    meta = node.get("metadata") or {}
    path = meta.get("path", "")
    url = meta.get("url", "")
    query = meta.get("query", node["label"])

    try:
        if action == "remove":
            node_store.remove(node_id)
            await send_nodes(ws)

        elif action in ("open", "launch", "play", "preview"):
            target = path or url or meta.get("name", node["label"])
            result = await asyncio.to_thread(_open_path, target)
            await send_action(ws, result)

        elif action == "summarize":
            if not path:
                await send_message(ws, "assistant", f"No file path stored for {node['label']}.")
                return
            await send_status(ws, "thinking")
            content = await asyncio.to_thread(_read_file, path)
            prompt = f"Summarize this file in a few sentences. Path: {path}\n\n{content[:4000]}"
            response, _ = await asyncio.to_thread(brain.chat, prompt, [])
            await send_message(ws, "assistant", response)
            await send_status(ws, "speaking")
            await asyncio.to_thread(voice.speak, strip_markdown(response), settings["voice_rate"])

        elif action == "read_aloud":
            if not path:
                await send_message(ws, "assistant", f"No file path stored for {node['label']}.")
                return
            await send_status(ws, "speaking")
            content = await asyncio.to_thread(_read_file, path)
            await asyncio.to_thread(voice.speak, content[:3000], settings["voice_rate"])

        elif action == "search_again":
            await send_status(ws, "thinking")
            results = await asyncio.to_thread(_web_search, query)
            prompt = f"I searched again for '{query}'. Here are the results:\n\n{results}\n\nGive me a brief summary of what's new."
            response, _ = await asyncio.to_thread(brain.chat, prompt, [])
            await send_message(ws, "assistant", response)
            await send_status(ws, "speaking")
            await asyncio.to_thread(voice.speak, strip_markdown(response), settings["voice_rate"])

        elif action == "complete":
            node_store.remove(node_id)
            await send_nodes(ws)
            await send_message(ws, "assistant", f"Marked '{node['label']}' as complete.")

    except Exception as e:
        await send_message(ws, "assistant", f"[Error: {e}]")
    finally:
        await send_status(ws, "idle")
        await send_action(ws, "")


async def handle_turn(ws: WebSocket, user_text: str, confirm):
    try:
        await send_status(ws, "thinking")
        lower = user_text.lower()

        for trigger in REMEMBER_TRIGGERS:
            if trigger in lower:
                fact = user_text[lower.index(trigger) + len(trigger):].strip().lstrip(",: ")
                if fact:
                    memory.store_fact(fact)
                    await send_action(ws, f"Storing explicit memory: {fact[:60]}...")
                break

        if is_morning_briefing_request(user_text):
            await send_action(ws, "Preparing morning briefing...")
            briefing_text = await asyncio.to_thread(briefer.generate)
            await send_message(ws, "assistant", briefing_text)
            await send_status(ws, "speaking")
            await asyncio.to_thread(voice.speak, briefing_text, settings["voice_rate"])

        elif is_computer_use_request(user_text):
            await send_action(ws, "Detected computer use request...")
            result = await computer.run_task_async(
                task=user_text,
                send_action_cb=lambda desc: send_action(ws, desc),
                confirm_cb=confirm,
            )
            await send_message(ws, "assistant", result)
            await asyncio.to_thread(voice.speak, strip_markdown(result), settings["voice_rate"])

        elif is_obsidian_save_request(user_text):
            await send_action(ws, "Saving to Obsidian vault...")
            format_prompt = (
                f"The user said: \"{user_text}\"\n\n"
                "Generate a concise Obsidian note. Reply with exactly:\n"
                "TITLE: <the note title>\nBODY:\n<the note body in markdown>"
            )
            raw, _ = await asyncio.to_thread(brain.chat, format_prompt)
            title, body = _parse_note_response(raw, user_text)
            rel_path = await asyncio.to_thread(obsidian.create_note, title, body)
            reply = f"Note saved to Obsidian: {rel_path}"
            await send_message(ws, "assistant", reply)
            await send_obsidian_event(ws, "note_created", {"path": rel_path, "title": title})
            await asyncio.to_thread(voice.speak, f"Note saved: {title}", settings["voice_rate"])

        elif is_obsidian_search_request(user_text):
            await send_action(ws, "Searching Obsidian vault...")
            results = await asyncio.to_thread(obsidian.search, user_text, 5)
            if results:
                await send_obsidian_event(ws, "search_results", {"results": results})
            relevant_memories = memory.retrieve(user_text)
            response, panels = await asyncio.to_thread(
                brain.chat, user_text, relevant_memories, results or None
            )
            for panel in panels:
                await ws.send_json({"type": "panel", **panel})
            await send_message(ws, "assistant", response)
            memory.store(user_text, response)
            await send_memories(ws)
            await send_status(ws, "speaking")
            await asyncio.to_thread(voice.speak, strip_markdown(response), settings["voice_rate"])

        else:
            await send_action(ws, "Retrieving relevant memories...")
            relevant_memories = memory.retrieve(user_text)

            await send_action(ws, "Searching Obsidian vault...")
            vault_notes = await asyncio.to_thread(obsidian.search, user_text)

            graph_context = None
            if is_graph_query(user_text):
                await send_action(ws, "Querying knowledge graph...")
                graph_context = await asyncio.to_thread(_run_graphify_query, user_text)

            await send_action(ws, "Calling Claude...")
            response, panels = await asyncio.to_thread(
                brain.chat, user_text, relevant_memories, vault_notes or None, graph_context
            )

            for panel in panels:
                await ws.send_json({"type": "panel", **panel})
            await send_message(ws, "assistant", response)
            await send_action(ws, "Storing memory...")
            memory.store(user_text, response)
            await send_memories(ws)
            await send_nodes(ws)

            # Background wiki ingest and self-learning
            asyncio.create_task(asyncio.to_thread(wiki.ingest, user_text, response))

            await send_status(ws, "speaking")
            await send_action(ws, "Speaking response...")
            await asyncio.to_thread(voice.speak, strip_markdown(response), settings["voice_rate"])

    except asyncio.CancelledError:
        raise
    except Exception as e:
        await send_message(ws, "assistant", f"[Error: {e}]")
    finally:
        await send_status(ws, "idle")
        await send_action(ws, "")

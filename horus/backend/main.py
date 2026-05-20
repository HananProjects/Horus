import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain import Brain
from voice import VoicePipeline
from memory import Memory
from computer_use import ComputerUseAgent
from obsidian import ObsidianVault

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

# Global settings
settings = {
    "computer_use_enabled": True,
    "wake_word_enabled": False,
    "voice_rate": 185,
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


async def send_status(ws: WebSocket, status: str):
    await ws.send_json({"type": "status", "status": status})


async def send_message(ws: WebSocket, role: str, content: str):
    await ws.send_json({"type": "message", "role": role, "content": content})


async def send_action(ws: WebSocket, action: str):
    await ws.send_json({"type": "action", "action": action})


async def send_memories(ws: WebSocket):
    await ws.send_json({"type": "memories", "memories": memory.get_all()})


async def send_settings(ws: WebSocket):
    await ws.send_json({"type": "settings", "settings": settings})


def is_computer_use_request(text: str) -> bool:
    if not settings["computer_use_enabled"]:
        return False
    lower = text.lower()
    return any(trigger in lower for trigger in COMPUTER_USE_TRIGGERS)


def is_obsidian_save_request(text: str) -> bool:
    lower = text.lower()
    return any(trigger in lower for trigger in OBSIDIAN_SAVE_TRIGGERS)


def is_obsidian_search_request(text: str) -> bool:
    lower = text.lower()
    return any(trigger in lower for trigger in OBSIDIAN_SEARCH_TRIGGERS)


async def send_obsidian_event(ws: WebSocket, event: str, data: dict):
    await ws.send_json({"type": "obsidian", "event": event, **data})


# Wake word background loop — broadcasts to all connected clients
connected_clients: list[WebSocket] = []
wake_word_task = None


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


@app.on_event("startup")
async def startup():
    global wake_word_task
    wake_word_task = asyncio.create_task(wake_word_loop())


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

    await send_status(ws, "idle")
    await send_memories(ws)
    await send_settings(ws)

    current_task = None

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "confirm_response":
                confirm_result["approved"] = data.get("approved", False)
                confirm_event.set()

            elif msg_type == "text":
                user_text = data.get("content", "")
                current_task = asyncio.create_task(
                    handle_turn(ws, user_text, request_confirmation)
                )

            elif msg_type == "voice_start":
                current_task = asyncio.create_task(
                    handle_voice_turn(ws, request_confirmation)
                )

            elif msg_type == "update_settings":
                new = data.get("settings", {})
                settings.update({k: v for k, v in new.items() if k in settings})
                await send_settings(ws)

            elif msg_type == "clear_memory":
                memory.clear()
                await send_memories(ws)
                await send_message(ws, "assistant", "Memory cleared.")

    except WebSocketDisconnect:
        connected_clients.remove(ws)
        if current_task:
            current_task.cancel()


async def handle_voice_turn(ws: WebSocket, confirm):
    await send_status(ws, "listening")
    await send_action(ws, "Recording audio...")
    user_text = await asyncio.to_thread(voice.listen)
    if not user_text:
        await send_status(ws, "idle")
        return
    await send_message(ws, "user", user_text)
    await handle_turn(ws, user_text, confirm)


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

        if is_computer_use_request(user_text):
            await send_action(ws, "Detected computer use request...")
            result = await computer.run_task_async(
                task=user_text,
                send_action_cb=lambda desc: send_action(ws, desc),
                confirm_cb=confirm,
            )
            await send_message(ws, "assistant", result)
            await asyncio.to_thread(voice.speak, result, settings["voice_rate"])

        elif is_obsidian_save_request(user_text):
            await send_action(ws, "Saving to Obsidian vault...")
            # Ask Claude to generate a title + clean note body
            format_prompt = (
                f"The user said: \"{user_text}\"\n\n"
                "Generate a concise Obsidian note from this. "
                "Reply with exactly two lines:\n"
                "TITLE: <the note title>\n"
                "BODY:\n<the note body in markdown>"
            )
            raw = await asyncio.to_thread(brain.chat, format_prompt)
            title, body = _parse_note_response(raw, user_text)
            rel_path = await asyncio.to_thread(obsidian.create_note, title, body)
            reply = f"Note saved to Obsidian: **{rel_path}**"
            await send_message(ws, "assistant", reply)
            await send_obsidian_event(ws, "note_created", {"path": rel_path, "title": title})
            await asyncio.to_thread(voice.speak, f"Note saved: {title}", settings["voice_rate"])

        elif is_obsidian_search_request(user_text):
            await send_action(ws, "Searching Obsidian vault...")
            results = await asyncio.to_thread(obsidian.search, user_text)
            if results:
                await send_obsidian_event(ws, "search_results", {"results": results})
            relevant_memories = memory.retrieve(user_text)
            response = await asyncio.to_thread(
                brain.chat, user_text, relevant_memories, results or None
            )
            await send_message(ws, "assistant", response)
            memory.store(user_text, response)
            await send_memories(ws)
            await send_status(ws, "speaking")
            await asyncio.to_thread(voice.speak, response, settings["voice_rate"])

        else:
            await send_action(ws, "Retrieving relevant memories...")
            relevant_memories = memory.retrieve(user_text)

            # Always do a passive vault search so Claude has note context
            await send_action(ws, "Searching Obsidian vault...")
            vault_notes = await asyncio.to_thread(obsidian.search, user_text)

            await send_action(ws, "Calling Claude...")
            response = await asyncio.to_thread(
                brain.chat, user_text, relevant_memories, vault_notes or None
            )

            await send_message(ws, "assistant", response)
            await send_action(ws, "Storing memory...")
            memory.store(user_text, response)
            await send_memories(ws)

            await send_status(ws, "speaking")
            await send_action(ws, "Speaking response...")
            await asyncio.to_thread(voice.speak, response, settings["voice_rate"])

    except asyncio.CancelledError:
        pass
    except Exception as e:
        await send_message(ws, "assistant", f"[Error: {e}]")
    finally:
        await send_status(ws, "idle")
        await send_action(ws, "")


def _parse_note_response(raw: str, fallback_title: str) -> tuple[str, str]:
    """Extract TITLE and BODY from Claude's note-formatting response."""
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

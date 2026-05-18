import asyncio
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain import Brain, _open_path, _read_file, _web_search
from voice import VoicePipeline
from memory import Memory
from computer_use import ComputerUseAgent
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
    await send_nodes(ws)

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

            elif msg_type == "remove_node":
                node_store.remove(data.get("node_id"))
                await send_nodes(ws)

            elif msg_type == "node_action":
                current_task = asyncio.create_task(
                    handle_node_action(ws, data.get("node_id"), data.get("action"))
                )

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
            prompt = f"Summarize this file for me in a few sentences. Path: {path}\n\n{content[:4000]}"
            response = await asyncio.to_thread(brain.chat, prompt, [])
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
            response = await asyncio.to_thread(brain.chat, prompt, [])
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

        if is_computer_use_request(user_text):
            await send_action(ws, "Detected computer use request...")
            result = await computer.run_task_async(
                task=user_text,
                send_action_cb=lambda desc: send_action(ws, desc),
                confirm_cb=confirm,
            )
            await send_message(ws, "assistant", result)
            await asyncio.to_thread(voice.speak, result, settings["voice_rate"])
        else:
            await send_action(ws, "Retrieving relevant memories...")
            relevant_memories = memory.retrieve(user_text)
            await send_action(ws, "Calling Claude...")

            response = await asyncio.to_thread(brain.chat, user_text, relevant_memories)

            await send_message(ws, "assistant", response)
            await send_action(ws, "Storing memory...")
            memory.store(user_text, response)
            await send_memories(ws)

            await send_nodes(ws)
            await send_status(ws, "speaking")
            await send_action(ws, "Speaking response...")
            await asyncio.to_thread(voice.speak, strip_markdown(response), settings["voice_rate"])

    except asyncio.CancelledError:
        pass
    except Exception as e:
        await send_message(ws, "assistant", f"[Error: {e}]")
    finally:
        await send_status(ws, "idle")
        await send_action(ws, "")

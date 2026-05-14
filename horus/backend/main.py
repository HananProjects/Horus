import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from brain import Brain
from voice import VoicePipeline
from memory import Memory

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


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


async def send_status(ws: WebSocket, status: str):
    await ws.send_json({"type": "status", "status": status})


async def send_message(ws: WebSocket, role: str, content: str):
    await ws.send_json({"type": "message", "role": role, "content": content})


async def send_action(ws: WebSocket, action: str):
    await ws.send_json({"type": "action", "action": action})


async def send_memories(ws: WebSocket):
    await ws.send_json({"type": "memories", "memories": memory.get_all()})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    await send_status(ws, "idle")
    await send_memories(ws)
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "text":
                user_text = data.get("content", "")
                await handle_turn(ws, user_text)

            elif msg_type == "voice_start":
                await send_status(ws, "listening")
                await send_action(ws, "Recording audio...")
                user_text = await asyncio.to_thread(voice.listen)
                if not user_text:
                    await send_status(ws, "idle")
                    continue
                await send_message(ws, "user", user_text)
                await handle_turn(ws, user_text)

    except WebSocketDisconnect:
        manager.disconnect(ws)


REMEMBER_TRIGGERS = ("remember that", "remember this", "don't forget", "note that", "keep in mind")


async def handle_turn(ws: WebSocket, user_text: str):
    try:
        await send_status(ws, "thinking")

        # Explicit memory storage
        lower = user_text.lower()
        for trigger in REMEMBER_TRIGGERS:
            if trigger in lower:
                fact = user_text[lower.index(trigger) + len(trigger):].strip().lstrip(",: ")
                if fact:
                    memory.store_fact(fact)
                    await send_action(ws, f"Storing explicit memory: {fact[:60]}...")
                break

        await send_action(ws, "Retrieving relevant memories...")
        relevant_memories = memory.retrieve(user_text)
        await send_action(ws, "Calling Claude...")

        response = await asyncio.to_thread(brain.chat, user_text, relevant_memories)

        await send_message(ws, "assistant", response)
        await send_action(ws, "Storing memory...")
        memory.store(user_text, response)
        await send_memories(ws)

        await send_status(ws, "speaking")
        await send_action(ws, "Speaking response...")
        await asyncio.to_thread(voice.speak, response)

    except Exception as e:
        await send_message(ws, "assistant", f"[Error: {e}]")
    finally:
        await send_status(ws, "idle")
        await send_action(ws, "")

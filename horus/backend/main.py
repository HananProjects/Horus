import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain import Brain
from voice import VoicePipeline
from memory import Memory
from computer_use import ComputerUseAgent

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


def is_computer_use_request(text: str) -> bool:
    lower = text.lower()
    return any(trigger in lower for trigger in COMPUTER_USE_TRIGGERS)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    # Per-connection confirmation state
    confirm_event = asyncio.Event()
    confirm_result = {"approved": False}

    async def request_confirmation(description: str) -> bool:
        confirm_event.clear()
        await ws.send_json({"type": "confirm_action", "description": description})
        await confirm_event.wait()
        return confirm_result["approved"]

    await send_status(ws, "idle")
    await send_memories(ws)

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

    except WebSocketDisconnect:
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

        # Explicit memory
        for trigger in REMEMBER_TRIGGERS:
            if trigger in lower:
                fact = user_text[lower.index(trigger) + len(trigger):].strip().lstrip(",: ")
                if fact:
                    memory.store_fact(fact)
                    await send_action(ws, f"Storing explicit memory: {fact[:60]}...")
                break

        # Computer use routing
        if is_computer_use_request(user_text):
            await send_action(ws, "Detected computer use request...")
            result = await computer.run_task_async(
                task=user_text,
                send_action_cb=lambda desc: send_action(ws, desc),
                confirm_cb=confirm,
            )
            await send_message(ws, "assistant", result)
            await asyncio.to_thread(voice.speak, result)
        else:
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

    except asyncio.CancelledError:
        pass
    except Exception as e:
        await send_message(ws, "assistant", f"[Error: {e}]")
    finally:
        await send_status(ws, "idle")
        await send_action(ws, "")

import asyncio
import base64
import io
import json
import os
import subprocess
import re
from pathlib import Path
from typing import Callable, Awaitable

import anthropic
import pyautogui
from PIL import ImageGrab
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SYSTEM_PROMPT = """You control a Mac computer on the user's behalf. Given a screenshot and a task, respond with ONLY a single valid JSON object — no explanation, no markdown, just raw JSON.

Available actions:
{"action": "open_app", "app": "Spotify"}
{"action": "click", "x": 100, "y": 200}
{"action": "double_click", "x": 100, "y": 200}
{"action": "right_click", "x": 100, "y": 200}
{"action": "type", "text": "hello world"}
{"action": "key", "key": "cmd+space"}
{"action": "scroll", "x": 500, "y": 400, "direction": "down", "amount": 3}
{"action": "done", "message": "Brief description of what was accomplished"}

Rules:
- Prefer open_app for launching applications — it is instant and reliable.
- Use done when the task is fully complete or cannot be completed.
- Output exactly one JSON object per response, nothing else."""


class ComputerUseAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-6"

    def _screenshot_b64(self) -> tuple[str, int, int]:
        img = ImageGrab.grab()
        w, h = img.size
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return b64, w, h

    def _call_claude(self, b64: str, task: str) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {"type": "text", "text": f"Task: {task}\n\nWhat is the single next action?"},
                    ],
                }
            ],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n")
        return json.loads(raw)

    async def run_task_async(
        self,
        task: str,
        send_action_cb: Callable[[str], Awaitable[None]],
        confirm_cb: Callable[[str], Awaitable[bool]],
    ) -> str:
        approved = await confirm_cb(f"Use computer to: {task}")
        if not approved:
            return "Action cancelled."

        for _ in range(10):
            await send_action_cb("Taking screenshot...")
            b64, _w, _h = await asyncio.to_thread(self._screenshot_b64)

            await send_action_cb("Asking Claude what to do next...")
            try:
                action = await asyncio.to_thread(self._call_claude, b64, task)
            except Exception as e:
                return f"Could not parse Claude's response: {e}"

            description = self._describe_action(action)
            await send_action_cb(description)

            if action["action"] == "done":
                return action.get("message", "Task complete.")

            await asyncio.to_thread(self._execute_action, action)

        return "Reached step limit."

    def _describe_action(self, action: dict) -> str:
        act = action.get("action", "")
        if act == "open_app":
            return f"Opening {action.get('app', '')}..."
        if act == "click":
            return f"Clicking at ({action['x']}, {action['y']})"
        if act == "double_click":
            return f"Double-clicking at ({action['x']}, {action['y']})"
        if act == "right_click":
            return f"Right-clicking at ({action['x']}, {action['y']})"
        if act == "type":
            return f"Typing: {action.get('text', '')[:50]}"
        if act == "key":
            return f"Pressing: {action.get('key', '')}"
        if act == "scroll":
            return f"Scrolling {action.get('direction', 'down')} at ({action['x']}, {action['y']})"
        if act == "done":
            return f"Done: {action.get('message', '')}"
        return str(action)

    def _execute_action(self, action: dict):
        act = action.get("action", "")

        if act == "open_app":
            try:
                os.startfile(action["app"])
            except Exception:
                subprocess.Popen(["cmd", "/c", "start", "", action["app"]], shell=False)

        elif act in ("click", "double_click", "right_click"):
            x, y = action["x"], action["y"]
            pyautogui.moveTo(x, y, duration=0.2)
            if act == "click":
                pyautogui.click()
            elif act == "double_click":
                pyautogui.doubleClick()
            elif act == "right_click":
                pyautogui.rightClick()

        elif act == "type":
            pyautogui.typewrite(action.get("text", ""), interval=0.04)

        elif act == "key":
            keys = action.get("key", "").split("+")
            pyautogui.hotkey(*keys)

        elif act == "scroll":
            x, y = action["x"], action["y"]
            direction = action.get("direction", "down")
            amount = action.get("amount", 3)
            pyautogui.moveTo(x, y)
            pyautogui.scroll(-amount if direction == "down" else amount)

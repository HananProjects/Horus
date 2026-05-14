import asyncio
import base64
import io
from pathlib import Path
from typing import Callable, Awaitable

import anthropic
import pyautogui
from PIL import ImageGrab
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SYSTEM_PROMPT = (
    "You are Horus, controlling the user's Mac on their behalf. "
    "You receive a screenshot and a task. Respond with the single most appropriate "
    "computer_use action to advance toward completing the task. Be precise with coordinates. "
    "When the task is complete, respond with text only (no tool call)."
)


class ComputerUseAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-opus-4-5"

    def _screenshot_b64(self) -> tuple[str, int, int]:
        img = ImageGrab.grab()
        w, h = img.size
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return b64, w, h

    def _call_claude(self, b64: str, w: int, h: int, task: str):
        return self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[
                {
                    "type": "computer_20241022",
                    "name": "computer",
                    "display_width_px": w,
                    "display_height_px": h,
                    "display_number": 1,
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {"type": "text", "text": task},
                    ],
                }
            ],
        )

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
            b64, w, h = await asyncio.to_thread(self._screenshot_b64)

            await send_action_cb("Asking Claude what to do next...")
            response = await asyncio.to_thread(self._call_claude, b64, w, h, task)

            text_blocks = [b for b in response.content if b.type == "text"]
            tool_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_blocks:
                return text_blocks[0].text if text_blocks else "Task complete."

            for tool_use in tool_blocks:
                action = tool_use.input
                description = self._describe_action(action)
                await send_action_cb(description)
                await asyncio.to_thread(self._execute_action, action)

        return "Reached step limit."

    def _describe_action(self, action: dict) -> str:
        act = action.get("action", "")
        if act == "mouse_move":
            return f"Moving mouse to ({action['coordinate'][0]}, {action['coordinate'][1]})"
        if act == "left_click":
            return f"Clicking at ({action['coordinate'][0]}, {action['coordinate'][1]})"
        if act == "right_click":
            return f"Right-clicking at ({action['coordinate'][0]}, {action['coordinate'][1]})"
        if act == "double_click":
            return f"Double-clicking at ({action['coordinate'][0]}, {action['coordinate'][1]})"
        if act == "type":
            return f"Typing: {action.get('text', '')[:50]}"
        if act == "key":
            return f"Pressing: {action.get('key', '')}"
        if act == "screenshot":
            return "Taking screenshot"
        if act == "scroll":
            return f"Scrolling {action.get('direction', '')} at ({action['coordinate'][0]}, {action['coordinate'][1]})"
        return str(action)

    def _execute_action(self, action: dict):
        act = action.get("action", "")
        coord = action.get("coordinate")

        if coord:
            x, y = coord
            pyautogui.moveTo(x, y, duration=0.25)

        if act == "left_click":
            pyautogui.click()
        elif act == "right_click":
            pyautogui.rightClick()
        elif act == "double_click":
            pyautogui.doubleClick()
        elif act == "mouse_move":
            pass  # already moved above
        elif act == "type":
            pyautogui.typewrite(action.get("text", ""), interval=0.04)
        elif act == "key":
            keys = action.get("key", "").split("+")
            pyautogui.hotkey(*keys)
        elif act == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 3)
            pyautogui.scroll(-amount if direction == "down" else amount)

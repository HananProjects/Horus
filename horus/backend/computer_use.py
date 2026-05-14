import base64
import io
import anthropic
import pyautogui
from PIL import ImageGrab
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are Horus, controlling the user's Mac on their behalf. You will receive a screenshot and a task. Respond with the single most appropriate computer_use action to advance toward completing the task. Be precise with coordinates."""


class ComputerUseAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-opus-4-5"  # computer use requires a capable model

    def screenshot_b64(self) -> tuple[str, int, int]:
        img = ImageGrab.grab()
        w, h = img.size
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return b64, w, h

    def run_task(self, task: str, on_action=None) -> str:
        """
        Run a computer-use task loop. Calls on_action(description) before each action.
        Returns a summary string when done.
        """
        for _ in range(10):  # max 10 steps
            b64, w, h = self.screenshot_b64()

            response = self.client.messages.create(
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

            # Check for text-only stop (task complete)
            text_blocks = [b for b in response.content if b.type == "text"]
            tool_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_blocks:
                return text_blocks[0].text if text_blocks else "Task complete."

            for tool_use in tool_blocks:
                action = tool_use.input
                description = self._describe_action(action)
                if on_action:
                    on_action(description)
                self._execute_action(action)

        return "Reached step limit."

    def _describe_action(self, action: dict) -> str:
        act = action.get("action", "")
        if act == "mouse_move":
            return f"Moving mouse to ({action['coordinate'][0]}, {action['coordinate'][1]})"
        if act == "left_click":
            return f"Clicking at ({action['coordinate'][0]}, {action['coordinate'][1]})"
        if act == "type":
            return f"Typing: {action['text'][:40]}"
        if act == "key":
            return f"Pressing key: {action['key']}"
        if act == "screenshot":
            return "Taking screenshot"
        return str(action)

    def _execute_action(self, action: dict):
        act = action.get("action", "")
        if act in ("mouse_move", "left_click", "right_click", "double_click"):
            x, y = action["coordinate"]
            pyautogui.moveTo(x, y, duration=0.3)
            if act == "left_click":
                pyautogui.click()
            elif act == "right_click":
                pyautogui.rightClick()
            elif act == "double_click":
                pyautogui.doubleClick()
        elif act == "type":
            pyautogui.typewrite(action["text"], interval=0.04)
        elif act == "key":
            pyautogui.hotkey(*action["key"].split("+"))
        elif act == "scroll":
            x, y = action["coordinate"]
            direction = action.get("direction", "down")
            amount = action.get("amount", 3)
            pyautogui.moveTo(x, y)
            dy = -amount if direction == "down" else amount
            pyautogui.scroll(dy)

import anthropic
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SYSTEM_PROMPT = """You are Horus, a highly capable personal AI assistant. You are precise, perceptive, and composed — named after the Egyptian god of the sky and protection, you see everything and act with purpose. You have access to the user's computer, persistent memory of past conversations, the ability to search the web for real-time information, and read/write access to the user's Obsidian knowledge vault.

When the user asks you to do something on their computer, describe what you are about to do before doing it. Always confirm before taking irreversible actions. Keep responses concise — the user will often be listening rather than reading.

The user's name is Hanan. You know he is a Computer Engineering graduate, currently job hunting in tech, working on personal projects to build his portfolio."""

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}


class Brain:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-6"
        self.history: list[dict] = []

    def chat(
        self,
        user_text: str,
        memories: Optional[list] = None,
        obsidian_notes: Optional[list] = None,
    ) -> str:
        memory_block = ""
        if memories:
            memory_block = "\n\n[Relevant memories from past conversations]\n" + "\n".join(f"- {m}" for m in memories)

        obsidian_block = ""
        if obsidian_notes:
            parts = []
            for note in obsidian_notes:
                parts.append(f"**{note['title']}** ({note['path']}):\n{note['snippet']}")
            obsidian_block = "\n\n[Relevant notes from Obsidian vault]\n" + "\n\n".join(parts)

        system = SYSTEM_PROMPT + memory_block + obsidian_block

        self.history.append({"role": "user", "content": user_text})

        # Agentic loop — handles web search tool calls automatically
        messages = list(self.history)
        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=[WEB_SEARCH_TOOL],
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                # Append assistant turn with tool calls, then tool results
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": block.input.get("query", ""),
                        })
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        # Extract final text reply
        reply = next(
            (block.text for block in response.content if hasattr(block, "text")),
            "I couldn't generate a response."
        )

        self.history.append({"role": "assistant", "content": reply})

        if len(self.history) > 40:
            self.history = self.history[-40:]

        return reply

    def reset(self):
        self.history = []

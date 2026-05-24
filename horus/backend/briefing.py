"""
Morning briefing generator for Horus.
Pulls weather, Apple Calendar events, and Obsidian wiki context,
then synthesizes a natural spoken briefing via Claude Sonnet.
"""

import subprocess
from datetime import datetime
from pathlib import Path

import requests
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_BRIEFING_WIKI_PAGES = [
    "Applications Pipeline",
    "Interview Prep",
    "Goals and Values",
    "Employment Timeline",
]

_CALENDAR_SCRIPT = """
set todayDate to current date
set midnight to todayDate - (time of todayDate)
set tomorrow to midnight + (24 * 60 * 60)
tell application "Calendar"
    set result to ""
    repeat with aCal in (every calendar)
        repeat with ev in (every event of aCal whose start date >= midnight and start date < tomorrow)
            set evTime to time string of (start date of ev)
            set result to result & (summary of ev) & " at " & evTime & linefeed
        end repeat
    end repeat
    return result
end tell
"""


class MorningBriefing:
    def __init__(self, wiki, vault):
        self.wiki = wiki
        self.vault = vault
        self._client = anthropic.Anthropic()

    def get_weather(self) -> str:
        try:
            r = requests.get("https://wttr.in/?format=j1", timeout=6)
            data = r.json()
            current = data["current_condition"][0]
            temp_f = current["temp_F"]
            temp_c = current["temp_C"]
            desc = current["weatherDesc"][0]["value"]
            feels_f = current["FeelsLikeF"]
            area = data["nearest_area"][0]["areaName"][0]["value"]
            return f"{temp_f}°F ({temp_c}°C), {desc}, feels like {feels_f}°F in {area}"
        except Exception:
            return ""

    def get_calendar(self) -> str:
        try:
            r = subprocess.run(
                ["osascript", "-e", _CALENDAR_SCRIPT],
                capture_output=True, text=True, timeout=10,
            )
            out = r.stdout.strip()
            return out if out else "No events scheduled today."
        except Exception:
            return ""

    def get_wiki_context(self) -> str:
        parts = []
        for page in _BRIEFING_WIKI_PAGES:
            try:
                content = self.wiki._read_page(page)
                if "_No information recorded yet._" not in content:
                    parts.append(f"=== {page} ===\n{content[:1000]}")
            except Exception:
                pass
        return "\n\n".join(parts)

    def generate(self) -> str:
        day_str = datetime.now().strftime("%A, %B %d")
        weather = self.get_weather()
        calendar = self.get_calendar()
        wiki = self.get_wiki_context()

        sections = [f"Today is {day_str}."]
        if weather:
            sections.append(f"Weather: {weather}")
        if calendar:
            sections.append(f"Today's calendar:\n{calendar}")
        if wiki:
            sections.append(f"Hanan's context:\n{wiki}")

        prompt = "\n\n".join(sections) + """

Write a spoken morning briefing for Hanan — natural and direct, like a smart assistant.
Structure (no headers, no bullets, just sentences):
1. Greet him with the day and date (1 sentence)
2. Weather — only if available (1 sentence)
3. Calendar highlights — only if there are events (1-2 sentences)
4. Job pipeline — what's most active or pressing right now (2-3 sentences, be specific about companies and stages)
5. One concrete focus for today (1 sentence)

Rules:
- No markdown, no bullet points — this is spoken aloud
- Under 200 words total
- Speak directly to Hanan: "you have", "your", not "the user"
- Be specific, not generic
"""

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system="You are Horus, Hanan's personal AI assistant. Write a morning briefing to be spoken aloud.",
            messages=[{"role": "user", "content": prompt}],
        )
        return next((b.text for b in response.content if hasattr(b, "text")), "Good morning, Hanan.")

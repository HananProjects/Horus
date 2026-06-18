"""
Post-conversation logger.
Runs in the background after every turn:
  1. Generates a one-line summary of the conversation via Haiku
  2. Appends a structured entry to B:\Obsidian Vault\log.md
  3. Rewrites the "Last updated" line in B:\Obsidian Vault\Projects\Horus.md
"""

import re
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

VAULT = Path(r"B:\Obsidian Vault")
LOG_FILE = VAULT / "log.md"
HORUS_PROJECT = VAULT / "Projects" / "Horus.md"


def _haiku_summary(user_text: str, assistant_text: str) -> str:
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f"Summarise this exchange in one short phrase (under 10 words, no period).\n\n"
                    f"User: {user_text[:300]}\nHorus: {assistant_text[:300]}"
                ),
            }],
        )
        return resp.content[0].text.strip().strip(".")
    except Exception:
        return user_text[:60].strip()


def _append_log(summary: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    entry = f"## [{date_str}] project | Horus — {summary}\n"
    try:
        if LOG_FILE.exists():
            existing = LOG_FILE.read_text(encoding="utf-8")
            LOG_FILE.write_text(existing + "\n" + entry, encoding="utf-8")
        else:
            LOG_FILE.write_text(entry, encoding="utf-8")
    except Exception as e:
        print(f"[conv_logger] log write error: {e}")


def _update_project_page(summary: str):
    try:
        if not HORUS_PROJECT.exists():
            return
        content = HORUS_PROJECT.read_text(encoding="utf-8")
        date_str = datetime.now().strftime("%Y-%m-%d")
        # Update "Last updated" line
        content = re.sub(
            r"\*\*Last updated:\*\*.*",
            f"**Last updated:** {date_str}",
            content,
        )
        # Update or insert "Last conversation" line
        last_conv_line = f"**Last conversation:** {summary}"
        if "**Last conversation:**" in content:
            content = re.sub(r"\*\*Last conversation:\*\*.*", last_conv_line, content)
        else:
            content = content.replace(
                "**Last updated:**",
                f"**Last updated:**",
            )
            content += f"\n{last_conv_line}\n"
        HORUS_PROJECT.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"[conv_logger] project page error: {e}")


def log_conversation(user_text: str, assistant_text: str):
    """Call this in a background thread after each turn."""
    summary = _haiku_summary(user_text, assistant_text)
    _append_log(summary)
    _update_project_page(summary)

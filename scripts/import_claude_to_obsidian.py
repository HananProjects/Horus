#!/usr/bin/env python3
"""
Import Claude conversation export into Obsidian vault.
Usage: python3 import_claude_to_obsidian.py <path-to-conversations.json>
       python3 import_claude_to_obsidian.py <path-to-export.zip>
"""

import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

VAULT = Path("/Users/hanan/Documents/Obsidian Vault")
OUT_DIR = VAULT / "Conversations" / "Claude"


def safe_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\n\r]', '', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name[:max_len] or "Untitled"


def parse_date(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def format_message(msg: dict) -> str:
    sender = msg.get("sender", "unknown")
    text = (msg.get("text") or "").strip()
    if not text:
        return ""
    role = "**Hanan**" if sender == "human" else "**Claude**"
    return f"{role}: {text}"


def conversation_to_markdown(convo: dict) -> str:
    name = convo.get("name") or "Untitled"
    summary = convo.get("summary") or ""
    created = parse_date(convo["created_at"])
    updated = parse_date(convo["updated_at"])
    messages = convo.get("chat_messages", [])

    # Sort messages by created_at
    messages = sorted(messages, key=lambda m: m.get("created_at", ""))

    lines = [
        "---",
        f'title: "{name}"',
        f"created: {created.strftime('%Y-%m-%d %H:%M')}",
        f"updated: {updated.strftime('%Y-%m-%d %H:%M')}",
        "tags: [claude, conversation]",
        "---",
        "",
        f"# {name}",
        "",
    ]

    if summary:
        lines += [f"> {summary}", ""]

    for msg in messages:
        formatted = format_message(msg)
        if formatted:
            lines.append(formatted)
            lines.append("")

    return "\n".join(lines)


def load_conversations(source: str) -> list[dict]:
    path = Path(source)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            with zf.open("conversations.json") as f:
                return json.load(f)
    else:
        with open(path) as f:
            return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import_claude_to_obsidian.py <conversations.json or export.zip>")
        sys.exit(1)

    source = sys.argv[1]
    conversations = load_conversations(source)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    created_count = 0
    skipped_count = 0

    for convo in conversations:
        name = convo.get("name") or "Untitled"
        messages = convo.get("chat_messages", [])

        # Skip empty conversations
        if not any((m.get("text") or "").strip() for m in messages):
            skipped_count += 1
            continue

        filename = safe_filename(name) + ".md"
        dest = OUT_DIR / filename

        # Avoid overwriting — append date suffix if collision
        if dest.exists():
            date_str = parse_date(convo["created_at"]).strftime("%Y%m%d")
            dest = OUT_DIR / f"{safe_filename(name)} ({date_str}).md"

        content = conversation_to_markdown(convo)
        dest.write_text(content, encoding="utf-8")
        created_count += 1
        print(f"  ✓ {dest.relative_to(VAULT)}")

    print(f"\nDone: {created_count} notes created, {skipped_count} empty conversations skipped.")
    print(f"Location: {OUT_DIR}")


if __name__ == "__main__":
    main()

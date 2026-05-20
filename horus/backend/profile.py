import json
from pathlib import Path

_FILE = Path(__file__).parent / "user_profile.json"

CATEGORIES = ["preferences", "habits", "goals", "dislikes", "projects", "facts", "communication"]

_SEED = {
    "preferences": [],
    "habits": [],
    "goals": [
        "Land a software engineering job in tech",
        "Build strong portfolio projects",
    ],
    "dislikes": [],
    "projects": [
        "Horus: personal AI assistant with neural sphere UI and voice control",
    ],
    "facts": [
        "Computer Engineering graduate",
        "Uses Windows PC",
        "Name is Hanan",
    ],
    "communication": [],
}


def load() -> dict:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    profile = {cat: list(items) for cat, items in _SEED.items()}
    save(profile)
    return profile


def save(profile: dict):
    _FILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def add_item(category: str, item: str) -> str:
    profile = load()
    if category not in profile:
        profile[category] = []
    item_clean = item.strip()
    item_lower = item_clean.lower()
    for existing in profile[category]:
        if existing.lower() == item_lower:
            return f"Already knew that about Hanan."
    profile[category].append(item_clean)
    profile[category] = profile[category][-30:]
    save(profile)
    return f"Noted: {item_clean}"


def to_prompt_block(profile: dict) -> str:
    sections = []
    for cat in CATEGORIES:
        items = profile.get(cat, [])
        if not items:
            continue
        label = cat.replace("_", " ").title()
        bullet_lines = "\n".join(f"  - {it}" for it in items[-12:])
        sections.append(f"{label}:\n{bullet_lines}")
    if not sections:
        return ""
    return "[What I know about Hanan]\n" + "\n\n".join(sections)

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

VAULT_PATH = Path("/Users/hanan/Documents/Obsidian Vault")
HORUS_FOLDER = "Horus"


class ObsidianVault:
    def __init__(self, vault_path: str = str(VAULT_PATH)):
        self.vault = Path(vault_path)
        self.horus_dir = self.vault / HORUS_FOLDER
        self.horus_dir.mkdir(exist_ok=True)

    def _all_notes(self) -> list[Path]:
        return [p for p in self.vault.rglob("*.md") if ".obsidian" not in str(p)]

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        """Keyword search across all vault notes. Returns title, path, snippet, score."""
        keywords = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 2]
        if not keywords:
            return []

        scored = []
        for path in self._all_notes():
            try:
                content = path.read_text(encoding="utf-8")
                text_lower = content.lower()
                score = sum(text_lower.count(kw) for kw in keywords)
                if score > 0:
                    scored.append({
                        "title": path.stem,
                        "path": str(path.relative_to(self.vault)),
                        "snippet": content[:400].strip(),
                        "score": score,
                    })
            except Exception:
                continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:max_results]

    def read_note(self, rel_path: str) -> Optional[str]:
        try:
            return (self.vault / rel_path).read_text(encoding="utf-8")
        except Exception:
            return None

    def create_note(self, title: str, content: str, folder: str = "") -> str:
        """Create a new note. Returns the relative path."""
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        dest_dir = (self.vault / folder) if folder else self.horus_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Avoid clobbering existing files
        base = dest_dir / f"{safe_title}.md"
        dest = base
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{safe_title} ({counter}).md"
            counter += 1

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        full_content = (
            f"---\ncreated: {timestamp}\ntags: [horus]\n---\n\n"
            f"# {title}\n\n{content}"
        )
        dest.write_text(full_content, encoding="utf-8")
        return str(dest.relative_to(self.vault))

    def append_to_note(self, rel_path: str, content: str) -> bool:
        try:
            path = self.vault / rel_path
            existing = path.read_text(encoding="utf-8")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            path.write_text(
                existing + f"\n\n---\n*{timestamp}*\n{content}",
                encoding="utf-8",
            )
            return True
        except Exception:
            return False

    def list_notes(self) -> list[dict]:
        notes = []
        for path in self._all_notes():
            try:
                stat = path.stat()
                notes.append({
                    "title": path.stem,
                    "path": str(path.relative_to(self.vault)),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                })
            except Exception:
                continue
        return sorted(notes, key=lambda x: x["modified"], reverse=True)

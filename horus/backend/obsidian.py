import re
from pathlib import Path
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

VAULT_PATH = Path("/Users/hanan/Documents/Obsidian Vault")
HORUS_FOLDER = "Horus"
VAULT_COLLECTION = "horus_vault"

# Notes with these names are noise (package files, not knowledge)
_EXCLUDED_NAMES = {"README.md", "LICENSE.md", "LICENSE", "CHANGELOG.md", "SECURITY.md"}
_EXCLUDED_DIRS = {".obsidian", "node_modules"}

# Only inject notes whose semantic distance is below this threshold (lower = more similar)
RELEVANCE_THRESHOLD = 1.3  # L2 distance — below this = semantically relevant


class ObsidianVault:
    def __init__(self, vault_path: str = str(VAULT_PATH), chroma_path: str = "./chroma_data"):
        self.vault = Path(vault_path)
        self.horus_dir = self.vault / HORUS_FOLDER
        self.horus_dir.mkdir(exist_ok=True)

        self._chroma = chromadb.PersistentClient(path=chroma_path)
        self._ef = embedding_functions.DefaultEmbeddingFunction()
        self._collection = self._chroma.get_or_create_collection(
            name=VAULT_COLLECTION,
            embedding_function=self._ef,
        )
        self._sync_index()

    # ── file helpers ──────────────────────────────────────────────────────────

    def _all_notes(self) -> list[Path]:
        return [
            p for p in self.vault.rglob("*.md")
            if not any(ex in str(p) for ex in _EXCLUDED_DIRS)
            and p.name not in _EXCLUDED_NAMES
        ]

    # ── indexing ──────────────────────────────────────────────────────────────

    def _sync_index(self):
        """Index any notes not yet in ChromaDB. Fast — skips already-indexed IDs."""
        existing_ids = set(self._collection.get(include=[])["ids"])
        to_add_ids, to_add_docs, to_add_meta = [], [], []

        for path in self._all_notes():
            doc_id = str(path.relative_to(self.vault))
            if doc_id in existing_ids:
                continue
            try:
                content = path.read_text(encoding="utf-8")
                to_add_ids.append(doc_id)
                to_add_docs.append(content[:3000])
                to_add_meta.append({"path": doc_id, "title": path.stem})
            except Exception:
                continue

        if to_add_ids:
            # Batch in groups of 50 to avoid embedding timeouts
            batch = 50
            for i in range(0, len(to_add_ids), batch):
                self._collection.add(
                    ids=to_add_ids[i:i+batch],
                    documents=to_add_docs[i:i+batch],
                    metadatas=to_add_meta[i:i+batch],
                )

    def _index_note(self, rel_path: str, content: str):
        """Upsert a single note into the semantic index."""
        self._collection.upsert(
            ids=[rel_path],
            documents=[content[:3000]],
            metadatas=[{"path": rel_path, "title": Path(rel_path).stem}],
        )

    # ── search ────────────────────────────────────────────────────────────────

    def search(self, query: str, n_results: int = 3) -> list[dict]:
        """Semantic search. Returns notes below RELEVANCE_THRESHOLD only."""
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            if dist < RELEVANCE_THRESHOLD:
                output.append({
                    "title": meta["title"],
                    "path": meta["path"],
                    "snippet": doc[:400].strip(),
                    "distance": round(dist, 3),
                })
        return output

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def read_note(self, rel_path: str) -> Optional[str]:
        try:
            return (self.vault / rel_path).read_text(encoding="utf-8")
        except Exception:
            return None

    def create_note(self, title: str, content: str, folder: str = "") -> str:
        """Create a new note and immediately index it. Returns the relative path."""
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        dest_dir = (self.vault / folder) if folder else self.horus_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / f"{safe_title}.md"
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
        rel_path = str(dest.relative_to(self.vault))
        self._index_note(rel_path, full_content)
        return rel_path

    def append_to_note(self, rel_path: str, content: str) -> bool:
        try:
            path = self.vault / rel_path
            existing = path.read_text(encoding="utf-8")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            updated = existing + f"\n\n---\n*{timestamp}*\n{content}"
            path.write_text(updated, encoding="utf-8")
            self._index_note(rel_path, updated)
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

"""
Horus self-coder — enables Horus to improve his own code based on learning discoveries.

Safety model (in order):
  1. Heuristic checks — instantly block dangerous patterns (exec, rmtree, etc.)
  2. Python AST parse — reject syntactically broken proposals
  3. Haiku LLM review — contextual safety review vs. the original file
  4. Git commit — every applied change is a tracked, revertible commit
"""

import ast
import asyncio
import re
import subprocess
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

REPO_ROOT = Path("/Users/hanan/Horus")

# Only these files can ever be modified by the self-coder
ALLOWED_FILES = [
    "horus/backend/learner.py",
    "horus/backend/main.py",
    "horus/backend/wiki.py",
    "horus/backend/brain.py",
]

# Patterns that hard-reject a proposal without LLM review
_BLOCKED_PATTERNS = [
    "os.system(", "__import__(", "eval(", "exec(",
    "shutil.rmtree", "os.remove", "os.unlink",
    "rmdir", "format_drive",
]

_SEP = "===CHANGE==="
_END = "===END==="


class SelfCoder:
    def __init__(self, vault):
        self.vault = vault
        self._client = anthropic.Anthropic()

    # ── public ──────────────────────────────────────────────────────────────

    async def evolve(self, discoveries: list[str]) -> list[str]:
        """Propose and safely apply code improvements from discoveries."""
        if not discoveries:
            return []
        proposals = await asyncio.to_thread(self._propose, discoveries)
        applied = []
        for p in proposals:
            ok = await asyncio.to_thread(self._review_and_apply, p)
            if ok:
                applied.append(f"Self-coded: {p['description']}")
        return applied

    # ── proposal generation ──────────────────────────────────────────────────

    def _read_files(self) -> dict[str, str]:
        return {
            rel: (REPO_ROOT / rel).read_text(encoding="utf-8")
            for rel in ALLOWED_FILES
            if (REPO_ROOT / rel).exists()
        }

    def _propose(self, discoveries: list[str]) -> list[dict]:
        files = self._read_files()
        files_block = "\n\n".join(f"=== {p} ===\n{c}" for p, c in files.items())
        disc_block = "\n".join(f"- {d}" for d in discoveries)

        prompt = f"""You are Horus, an AI assistant that safely improves your own code.

Discoveries from the latest learning cycle:
{disc_block}

Your modifiable files:
{files_block}

Based on the discoveries, propose 0-3 minimal, targeted improvements.
Good candidates: adding items to config lists (WATCH_TOPICS, WIKI_PAGES,
trigger tuples), updating the system prompt with newly learned facts about
Hanan, or small additive utility improvements that directly follow from
what was learned.

For each proposed change output exactly:
{_SEP}
FILE: <one of the modifiable relative paths>
DESCRIPTION: <one sentence — what changes and why>
FULL_FILE_CONTENT:
<the complete new file content>
{_END}

If nothing warrants a change, output exactly: NO_CHANGES

Hard rules:
- Only modify the listed files
- Never remove existing functionality or safety checks
- Never add new subprocess calls, file deletions, or outbound network calls
- Prefer additive config-level changes over structural rewrites"""

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=6000,
            system="You are a careful software engineer improving an AI assistant's own codebase.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next((b.text for b in response.content if hasattr(b, "text")), "")

        if "NO_CHANGES" in raw:
            return []
        return self._parse(raw)

    def _parse(self, raw: str) -> list[dict]:
        proposals = []
        for chunk in raw.split(_SEP)[1:]:
            end = chunk.find(_END)
            if end != -1:
                chunk = chunk[:end]
            fm = re.search(r"FILE:\s*(.+)", chunk)
            dm = re.search(r"DESCRIPTION:\s*(.+)", chunk)
            cm = re.search(r"FULL_FILE_CONTENT:\n(.*)", chunk, re.DOTALL)
            if fm and dm and cm:
                proposals.append({
                    "file": fm.group(1).strip(),
                    "description": dm.group(1).strip(),
                    "content": cm.group(1).strip(),
                })
        return proposals

    # ── safety gates ────────────────────────────────────────────────────────

    def _heuristic_ok(self, content: str) -> bool:
        return not any(p in content for p in _BLOCKED_PATTERNS)

    def _syntax_ok(self, content: str) -> bool:
        try:
            ast.parse(content)
            return True
        except SyntaxError:
            return False

    def _llm_review_ok(self, rel_path: str, original: str, proposed: str) -> bool:
        review = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="You are a strict security reviewer for AI self-modification.",
            messages=[{"role": "user", "content": (
                f"Review this proposed self-modification to `{rel_path}`.\n\n"
                f"=== Original (first 2000 chars) ===\n{original[:2000]}\n\n"
                f"=== Proposed (first 2000 chars) ===\n{proposed[:2000]}\n\n"
                "Does the proposed version introduce any of: shell injection, "
                "unauthorized file deletion, data exfiltration, removal of "
                "existing safety checks, infinite loops, or obfuscated code?\n\n"
                "Reply with exactly:\nSAFE: <one line reason>\nor\nUNSAFE: <one line reason>"
            )}],
        )
        result = next((b.text for b in review.content if hasattr(b, "text")), "UNSAFE: no response")
        return result.strip().upper().startswith("SAFE")

    # ── apply ────────────────────────────────────────────────────────────────

    def _review_and_apply(self, proposal: dict) -> bool:
        rel_path = proposal["file"]
        new_content = proposal["content"]
        description = proposal["description"]

        if rel_path not in ALLOWED_FILES:
            return False

        abs_path = REPO_ROOT / rel_path
        if not abs_path.exists():
            return False

        original = abs_path.read_text(encoding="utf-8")
        if original.strip() == new_content.strip():
            return False  # no-op

        # Gate 1: heuristics
        if not self._heuristic_ok(new_content):
            self._log_rejection(rel_path, description, "failed heuristic check")
            return False

        # Gate 2: Python syntax
        if rel_path.endswith(".py") and not self._syntax_ok(new_content):
            self._log_rejection(rel_path, description, "syntax error in proposed code")
            return False

        # Gate 3: LLM review
        if not self._llm_review_ok(rel_path, original, new_content):
            self._log_rejection(rel_path, description, "failed LLM safety review")
            return False

        # Apply
        abs_path.write_text(new_content, encoding="utf-8")

        # Git commit — makes every change reversible
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "add", rel_path],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "commit", "-m",
                 f"[horus self-code {ts}] {description}\n\n"
                 "Co-Authored-By: Horus <horus@self>"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

        self.vault.create_note(
            description[:70].strip(),
            f"**File:** `{rel_path}`\n**Change:** {description}\n\n**Related:** [[Horus Project]]",
            "Horus",
        )
        return True

    def _log_rejection(self, rel_path: str, description: str, reason: str):
        self.vault.create_note(
            f"Rejected: {description[:55].strip()}",
            f"**File:** `{rel_path}`\n**Proposed:** {description}\n**Reason:** {reason}\n\n**Related:** [[Horus Project]]",
            "Horus",
        )

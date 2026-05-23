"""
Autonomous learning loop for Horus.

Every N hours: lints wiki for knowledge gaps and fills them via web search,
checks for Claude/AI news, discovers new Claude Code skills on GitHub,
reviews their code before auto-installing.
"""

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from self_coder import SelfCoder

load_dotenv(Path(__file__).parent.parent / ".env")

SKILLS_DIR = Path.home() / ".claude" / "skills"
LEARNING_INTERVAL_HOURS = 6

_WEB_TOOL = {"type": "web_search_20250305", "name": "web_search"}

# Topics Horus proactively stays current on
_WATCH_TOPICS = [
    "Anthropic Claude new model or API feature releases 2025",
    "new Claude Code slash commands or skills released on GitHub 2025",
    "new graduate software engineer job market trends and hiring outlook 2025",
]


class HorusLearner:
    def __init__(self, wiki, vault):
        self.wiki = wiki
        self.vault = vault
        self._client = anthropic.Anthropic()
        self._self_coder = SelfCoder(vault)

    # ── public ──────────────────────────────────────────────────────────────

    async def run_cycle(self) -> list[str]:
        """Full autonomous learning cycle. Returns list of discovery strings."""
        discoveries: list[str] = []

        discoveries += await self._fill_wiki_gaps()
        discoveries += await self._check_current_topics()
        discoveries += await self._discover_and_install_skills()

        # Self-coding phase — apply safe code improvements from discoveries
        coding_results = await self._self_coder.evolve(discoveries)
        discoveries += coding_results

        if discoveries:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            body = "\n".join(f"- {d}" for d in discoveries)
            await asyncio.to_thread(
                self.vault.create_note,
                f"Horus Learning Log {ts}",
                f"## Learning cycle — {ts}\n\n{body}",
                "Horus",
            )

        return discoveries

    # ── core call primitive ──────────────────────────────────────────────────

    def _call(
        self,
        system: str,
        user: str,
        web: bool = False,
        max_tokens: int = 800,
    ) -> str:
        """Stateless Haiku call, optionally with built-in web search."""
        messages: list[dict] = [{"role": "user", "content": user}]
        kwargs: dict = dict(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        if web:
            kwargs["tools"] = [_WEB_TOOL]

        while True:
            response = self._client.messages.create(**kwargs)
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                results = [
                    {"type": "tool_result", "tool_use_id": b.id, "content": b.input.get("query", "")}
                    for b in response.content
                    if b.type == "tool_use"
                ]
                messages.append({"role": "user", "content": results})
                kwargs["messages"] = messages
            else:
                break

        return next((b.text for b in response.content if hasattr(b, "text")), "")

    # ── phase 1: wiki gap filling ────────────────────────────────────────────

    async def _fill_wiki_gaps(self) -> list[str]:
        lint_report = await asyncio.to_thread(self.wiki.lint)
        if not lint_report:
            return []

        questions_raw = await asyncio.to_thread(
            self._call,
            "You identify actionable knowledge gaps.",
            f"These gaps exist in a personal knowledge wiki:\n{lint_report}\n\n"
            "List up to 3 specific research questions to fill them. "
            "One question per line, no bullets, no numbering. Output questions only.",
        )

        questions = [q.strip() for q in questions_raw.splitlines() if q.strip() and len(q) > 15][:3]

        discoveries = []
        for q in questions:
            answer = await asyncio.to_thread(
                self._call,
                "You are a concise research assistant writing for a personal knowledge base.",
                f"Research and answer this question:\n{q}",
                True,
            )
            if answer and len(answer) > 80:
                await asyncio.to_thread(self.wiki.ingest, q, answer)
                discoveries.append(f"Filled wiki gap: {q[:70]}")

        return discoveries

    # ── phase 2: current topics ──────────────────────────────────────────────

    async def _check_current_topics(self) -> list[str]:
        discoveries = []
        for topic in _WATCH_TOPICS:
            result = await asyncio.to_thread(
                self._call,
                "You report new developments concisely.",
                f"Search for recent developments: {topic}. "
                "Summarize any new findings in 2-3 sentences. "
                "If nothing notable or new, respond with exactly: nothing new",
                True,
            )
            if result and "nothing new" not in result.lower() and len(result) > 80:
                await asyncio.to_thread(self.wiki.ingest, f"Research: {topic}", result)
                discoveries.append(f"Updated knowledge: {topic[:60]}")

        return discoveries

    # ── phase 3: skill discovery & install ──────────────────────────────────

    async def _discover_and_install_skills(self) -> list[str]:
        search_result = await asyncio.to_thread(
            self._call,
            "You are a developer researching tools.",
            "Search GitHub for Claude Code skills — repos containing a SKILL.md file "
            "intended for use with the Claude Code CLI. "
            "List each as: SKILL_NAME | GITHUB_CLONE_URL\n"
            "Include only genuine Claude Code skills with a real SKILL.md. "
            "If none found, output exactly: NONE",
            True,
        )

        if not search_result or "NONE" in search_result.upper():
            return []

        discoveries = []
        for line in search_result.splitlines():
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|", 1)]
            if len(parts) < 2:
                continue
            skill_name, clone_url = parts
            # Sanitize skill name to a safe directory name
            skill_name = "".join(c for c in skill_name if c.isalnum() or c in "-_").lower()
            if not skill_name or not clone_url.startswith("https://github.com"):
                continue

            skill_dest = SKILLS_DIR / skill_name
            if skill_dest.exists():
                updated = await asyncio.to_thread(self._pull_skill, skill_name)
                if updated:
                    discoveries.append(f"Updated skill: {skill_name}")
                continue

            installed = await asyncio.to_thread(
                self._review_and_install, skill_name, clone_url
            )
            if installed:
                discoveries.append(f"Installed new skill: {skill_name} ({clone_url})")

        return discoveries

    def _pull_skill(self, skill_name: str) -> bool:
        """git pull an existing skill. Returns True if it was updated."""
        try:
            r = subprocess.run(
                ["git", "-C", str(SKILLS_DIR / skill_name), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=15,
            )
            return r.returncode == 0 and "up to date" not in r.stdout.lower()
        except Exception:
            return False

    def _review_and_install(self, skill_name: str, clone_url: str) -> bool:
        """Clone to temp dir, run a Haiku code review, install if safe."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / skill_name
            try:
                r = subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, str(tmp_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    return False
            except Exception:
                return False

            # Collect reviewable files (SKILL.md + code files)
            code_parts = []
            for pattern in ("SKILL.md", "*.py", "*.sh", "*.js", "*.ts"):
                for f in sorted(tmp_path.rglob(pattern)):
                    if "node_modules" in str(f) or ".git" in str(f):
                        continue
                    try:
                        code_parts.append(f"=== {f.name} ===\n{f.read_text(errors='ignore')[:2000]}")
                    except Exception:
                        continue

            if not code_parts:
                return False

            review = self._call(
                "You are a security-focused code reviewer. Be strict about safety.",
                "Review this Claude Code skill for safety before auto-installation. "
                "Look for: shell injections, data exfiltration, destructive file ops, "
                "network calls to unexpected hosts, or obfuscated code.\n\n"
                + "\n\n".join(code_parts[:6])
                + "\n\nRespond with exactly one of:\n"
                "SAFE: <one-line reason>\n"
                "UNSAFE: <one-line reason>",
                max_tokens=200,
            )

            if not review.upper().startswith("SAFE"):
                self.vault.create_note(
                    f"Skill Review Rejected — {skill_name}",
                    f"**Skill:** `{skill_name}`\n**Source:** {clone_url}\n\n"
                    f"**Review result:**\n{review}",
                    "Horus",
                )
                return False

            try:
                SKILLS_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copytree(tmp_path, SKILLS_DIR / skill_name)
                return True
            except Exception:
                return False
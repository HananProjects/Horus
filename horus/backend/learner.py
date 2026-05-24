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
from ddgs import DDGS
from self_coder import SelfCoder

load_dotenv(Path(__file__).parent.parent / ".env")

SKILLS_DIR = Path.home() / ".claude" / "skills"
LEARNING_INTERVAL_HOURS = 6

_DISCOVERY_PREFIXES = (
    "Filled wiki gap: ", "Updated knowledge: ",
    "Installed new skill: ", "Updated skill: ", "Self-coded: ",
)

# Keywords → wiki page links. Order matters: first match wins per discovery.
_WIKI_LINK_MAP = [
    (("interview", "tenstorrent", "two dots", "offer", "pipeline"), "[[Interview Prep]]"),
    (("application", "apply", "applied", "company", "hiring", "recruit"), "[[Applications Pipeline]]"),
    (("job", "career", "employment", "full-time", "new grad"), "[[Job Search]]"),
    (("claude", "anthropic", "model", "api", "skill", "github"), "[[Technical Skills]]"),
    (("learn", "course", "study", "growth", "read"), "[[Learning and Growth]]"),
    (("horus", "backend", "frontend", "self-cod", "daemon"), "[[Horus Project]]"),
    (("goal", "value", "priority", "life", "personal"), "[[Goals and Values]]"),
    (("employment", "start date", "onboarding", "relocation", "deadline"), "[[Employment Timeline]]"),
    (("tenstorrent", "priority compan", "target compan", "culture", "tech stack"), "[[Companies of Interest]]"),
]

# Topics Horus proactively stays current on
_WATCH_TOPICS = [
    "Anthropic Claude new model or API feature releases 2025",
    "new Claude Code slash commands or skills released on GitHub 2025",
    "new graduate software engineer job market trends and hiring outlook 2025",
    "software engineering new grad full-time offer timelines and start dates 2025",
    "long-term career paths for software engineers values-driven tech companies 2025",
    "software engineering technical interview preparation resources and strategies 2025",
    "top AI chip and hardware companies hiring new grad software engineers 2025",
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

            # Derive a specific title from the most meaningful discovery
            title_src = discoveries[0]
            for prefix in _DISCOVERY_PREFIXES:
                title_src = title_src.replace(prefix, "")
            title = title_src[:70].strip()

            # Find which wiki pages this cycle touched
            all_text = " ".join(discoveries).lower()
            links = []
            seen = set()
            for keywords, link in _WIKI_LINK_MAP:
                if link not in seen and any(k in all_text for k in keywords):
                    links.append(link)
                    seen.add(link)

            body_lines = "\n".join(f"- {d}" for d in discoveries)
            body = f"## {ts}\n\n{body_lines}"
            if links:
                body += f"\n\n**Related:** {' '.join(links)}"

            await asyncio.to_thread(self.vault.create_note, title, body, "Horus")

        return discoveries

    # ── core call primitive ──────────────────────────────────────────────────

    def _search(self, query: str) -> str:
        """DuckDuckGo search, returns formatted results string."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            parts = [f"{r['title']}\n{r['body']}\nSource: {r['href']}" for r in results]
            return "\n\n".join(parts) if parts else "No results found."
        except Exception as e:
            return f"Search failed: {e}"

    def _call(
        self,
        system: str,
        user: str,
        web: bool = False,
        max_tokens: int = 800,
    ) -> str:
        """Stateless Haiku call. If web=True, prepends DuckDuckGo results to the prompt."""
        if web:
            search_results = self._search(user[:300])
            user = f"Web search results:\n{search_results}\n\nUsing the above, answer:\n{user}"

        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
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
            search_results = await asyncio.to_thread(self._search, q)
            answer = await asyncio.to_thread(
                self._call,
                "You are a concise research assistant writing for a personal knowledge base.",
                f"Search results:\n{search_results}\n\nUsing the above, answer:\n{q}",
            )
            if answer and len(answer) > 80:
                await asyncio.to_thread(self.wiki.ingest, q, answer)
                discoveries.append(f"Filled wiki gap: {q[:70]}")

        return discoveries

    # ── phase 2: current topics ──────────────────────────────────────────────

    async def _check_current_topics(self) -> list[str]:
        discoveries = []
        for topic in _WATCH_TOPICS:
            search_results = await asyncio.to_thread(self._search, topic)
            result = await asyncio.to_thread(
                self._call,
                "You report new developments concisely.",
                f"Search results:\n{search_results}\n\n"
                f"Based on these results, summarize any new developments about: {topic}\n"
                "2-3 sentences max. If nothing notable, respond with exactly: nothing new",
            )
            if result and "nothing new" not in result.lower() and len(result) > 80:
                await asyncio.to_thread(self.wiki.ingest, f"Research: {topic}", result)
                discoveries.append(f"Updated knowledge: {topic[:60]}")

        return discoveries

    # ── phase 3: skill discovery & install ──────────────────────────────────

    async def _discover_and_install_skills(self) -> list[str]:
        # Step 1: targeted GitHub searches
        raw1 = await asyncio.to_thread(self._search, 'site:github.com "SKILL.md" "claude code" skill')
        raw2 = await asyncio.to_thread(self._search, "github claude code CLI SKILL.md slash command skill repository")
        combined = raw1 + "\n\n" + raw2

        # Step 2: extract real clone URLs from search results
        parsed = await asyncio.to_thread(
            self._call,
            "You extract GitHub repo URLs from search results.",
            f"Search results:\n{combined}\n\n"
            "List the GitHub repo clone URLs for repos that contain Claude Code SKILL.md files. "
            "Output one URL per line, format: https://github.com/user/repo\n"
            "Only include URLs clearly visible in the search results. If none, output: NONE",
        )

        if not parsed or "NONE" in parsed.upper():
            return []

        # Deduplicate URLs
        repo_urls = []
        seen_urls = set()
        for line in parsed.splitlines():
            line = line.strip().rstrip("/")
            if line.startswith("https://github.com/") and line not in seen_urls:
                # Normalize: strip .git, strip paths beyond user/repo
                parts = line.replace("https://github.com/", "").split("/")
                if len(parts) >= 2:
                    url = f"https://github.com/{parts[0]}/{parts[1]}"
                    if url not in seen_urls:
                        repo_urls.append(url)
                        seen_urls.add(url)

        discoveries = []
        for clone_url in repo_urls[:5]:  # cap at 5 repos per cycle
            installed = await asyncio.to_thread(self._clone_and_install_all, clone_url)
            discoveries.extend(installed)

        return discoveries

    def _clone_and_install_all(self, clone_url: str) -> list[str]:
        """Clone a repo, find every SKILL.md (root or subdirs), install each as a separate skill."""
        installed = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "repo"
            try:
                r = subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, str(tmp_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    return []
            except Exception:
                return []

            # Find every directory that contains a SKILL.md
            skill_dirs = [
                sm.parent for sm in tmp_path.rglob("SKILL.md")
                if ".git" not in str(sm)
            ]

            for skill_dir in skill_dirs:
                # Derive skill name from SKILL.md frontmatter name: field, else dir name
                skill_name = self._read_skill_name(skill_dir)
                if not skill_name:
                    continue

                skill_dest = SKILLS_DIR / skill_name
                if skill_dest.exists():
                    continue  # already installed

                ok = self._review_and_install_dir(skill_name, skill_dir, clone_url)
                if ok:
                    installed.append(f"Installed new skill: {skill_name} (from {clone_url})")

        return installed

    def _read_skill_name(self, skill_dir: Path) -> str:
        """Extract `name:` from SKILL.md frontmatter, fallback to directory name."""
        try:
            text = (skill_dir / "SKILL.md").read_text(errors="ignore")
            for line in text.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"').strip("'")
                    sanitized = "".join(c for c in name if c.isalnum() or c in "-_").lower()
                    if sanitized:
                        return sanitized
        except Exception:
            pass
        name = skill_dir.name
        return "".join(c for c in name if c.isalnum() or c in "-_").lower() or ""

    def _review_and_install_dir(self, skill_name: str, skill_dir: Path, source_url: str) -> bool:
        """Review a single skill directory and install it if safe."""
        code_parts = []
        for pattern in ("SKILL.md", "*.py", "*.sh", "*.js", "*.ts"):
            for f in sorted(skill_dir.rglob(pattern)):
                if "node_modules" in str(f) or ".git" in str(f):
                    continue
                try:
                    code_parts.append(f"=== {f.name} ===\n{f.read_text(errors='ignore')[:2000]}")
                except Exception:
                    continue

        if not code_parts:
            return False

        review = self._call(
            "You are a security-focused code reviewer.",
            "Review this Claude Code skill for auto-installation safety. "
            "Only reject if it contains clearly malicious patterns: "
            "credential exfiltration to external servers, intentional data destruction (rm -rf on user dirs), "
            "obfuscated/encoded payloads, or backdoors. "
            "Normal subprocess calls, shell commands, network API calls, and file read/write ops are SAFE — "
            "these are expected in Claude Code skills.\n\n"
            + "\n\n".join(code_parts[:6])
            + "\n\nRespond with exactly one of:\n"
            "SAFE: <one-line reason>\n"
            "UNSAFE: <one-line reason>",
            max_tokens=200,
        )

        if "UNSAFE:" in review.upper()[:200]:
            return False

        try:
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill_dir, SKILLS_DIR / skill_name)
            return True
        except Exception:
            return False
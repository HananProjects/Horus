"""
LLM Wiki pattern (inspired by Karpathy):
After each conversation turn, a cheap background LLM call compiles insights
into structured wiki pages in Obsidian. Future queries hit compiled, synthesized
knowledge instead of raw transcripts — fewer tokens, better answers.
"""

import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

WIKI_FOLDER = "Wiki"

WIKI_PAGES = {
    "Hanan Profile":   "Personal background, personality, values, life situation, relationships",
    "Job Search":      "Job applications, interviews, companies, roles, status, recruiter contacts",
    "Technical Skills":"Programming languages, frameworks, tools, projects, strengths/gaps",
    "Personal Life":   "Interests, hobbies, travel, purchases, goals outside of work",
    "Horus Project":   "Horus assistant features, architecture decisions, bugs, roadmap",
    "Goals and Values":"Short and long-term goals, core values, motivations, priorities in life",
    "Learning and Growth": "Topics Hanan is actively learning, books being read, courses, skills being developed",
}

_INGEST_PROMPT = """\
You maintain a personal knowledge wiki for Hanan's AI assistant (Horus).

Below are the current wiki pages and a new conversation turn. For each wiki page \
that gained new information from this conversation, output an updated version.

Format your response as:
===PAGE: <exact page title>===
<complete updated page content in markdown — preserve existing facts, only add/correct>

If a page needs no update, skip it entirely. If nothing needs updating, output: NO_UPDATE

Current wiki pages:
{pages}

New conversation turn:
User: {user_text}
Horus: {assistant_text}
"""


class WikiManager:
    def __init__(self, vault):
        self.vault = vault  # ObsidianVault instance
        self.client = anthropic.Anthropic()
        self.wiki_dir = vault.vault / WIKI_FOLDER
        self.wiki_dir.mkdir(exist_ok=True)
        self._ensure_pages()

    def _ensure_pages(self):
        for title in WIKI_PAGES:
            path = self.wiki_dir / f"{title}.md"
            if not path.exists():
                path.write_text(f"# {title}\n\n_No information recorded yet._\n", encoding="utf-8")

    def _read_page(self, title: str) -> str:
        try:
            return (self.wiki_dir / f"{title}.md").read_text(encoding="utf-8")
        except Exception:
            return f"# {title}\n\n_No information recorded yet._\n"

    def _write_page(self, title: str, content: str):
        path = self.wiki_dir / f"{title}.md"
        path.write_text(content, encoding="utf-8")
        rel = str(path.relative_to(self.vault.vault))
        self.vault._index_note(rel, content)

    def ingest(self, user_text: str, assistant_text: str):
        """
        One Haiku call compiles the conversation into relevant wiki pages.
        Runs in a background thread — never blocks the main response.
        """
        pages_block = "\n\n".join(
            f"--- {title} ({desc}) ---\n{self._read_page(title)}"
            for title, desc in WIKI_PAGES.items()
        )

        prompt = _INGEST_PROMPT.format(
            pages=pages_block,
            user_text=user_text[:800],
            assistant_text=assistant_text[:600],
        )

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw == "NO_UPDATE":
                return

            # Parse ===PAGE: Title=== blocks — only write to known page titles
            valid_titles = set(WIKI_PAGES.keys())
            current_title = None
            current_lines: list[str] = []

            for line in raw.splitlines():
                if line.startswith("===PAGE:") and line.endswith("==="):
                    if current_title and current_lines:
                        self._write_page(current_title, "\n".join(current_lines).strip())
                    raw_title = line[8:-3].strip()
                    # Match to known titles (strip any trailing description the LLM added)
                    current_title = next(
                        (t for t in valid_titles if raw_title.startswith(t)), None
                    )
                    current_lines = []
                elif current_title:
                    current_lines.append(line)

            if current_title and current_lines:
                self._write_page(current_title, "\n".join(current_lines).strip())

        except Exception:
            pass  # Background task — silently skip on error

    def lint(self):
        """
        Periodic health check: ask Claude to flag contradictions, stale info, or gaps.
        Call manually or on a schedule, not after every turn.
        """
        pages_block = "\n\n".join(
            f"--- {title} ---\n{self._read_page(title)}" for title in WIKI_PAGES
        )
        prompt = (
            "Review these personal knowledge wiki pages for contradictions, stale info, "
            "orphaned facts, or obvious gaps. List issues as bullet points. "
            "Be concise.\n\n" + pages_block
        )
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception:
            return None
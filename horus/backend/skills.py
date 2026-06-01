"""
Skill router for Horus.

At startup, indexes all SKILL.md files in ~/.claude/skills/ by parsing
the `description:` frontmatter field. On each turn, scores skills against
the user's message and injects the best match into the brain call.
"""

import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SKILLS_DIR = Path.home() / ".claude" / "skills"

# Only invoke skill routing if the message is long enough to be meaningful
MIN_MSG_LEN = 8

# Score threshold — below this, no skill is injected
SCORE_THRESHOLD = 2

# Stop words to ignore in scoring
_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "i", "you", "me", "my",
    "your", "we", "our", "it", "its", "this", "that", "and", "or", "but",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "about",
    "how", "what", "when", "where", "who", "which", "why", "want", "need",
    "help", "use", "used", "using", "make", "create", "build", "get",
    "give", "show", "tell", "let", "please", "horus", "hey", "hi",
}


def _parse_frontmatter(text: str) -> dict:
    """Extract name and description from SKILL.md YAML frontmatter."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _tokenize(text: str) -> set[str]:
    """Lowercase words, strip punctuation, remove stop words."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


class SkillRouter:
    def __init__(self):
        self._catalog: list[dict] = []   # [{name, description, tokens, path}]
        self._client = anthropic.Anthropic()
        self._loaded = False

    def load(self):
        """Parse all SKILL.md files. Call once at startup (runs in a thread)."""
        catalog = []
        if not SKILLS_DIR.exists():
            self._loaded = True
            return
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text(errors="ignore")
                fm = _parse_frontmatter(text)
                name = fm.get("name") or skill_dir.name
                desc = fm.get("description", "")
                if not desc:
                    continue
                tokens = _tokenize(f"{name} {desc}")
                catalog.append({
                    "name": name,
                    "description": desc,
                    "tokens": tokens,
                    "path": skill_md,
                })
            except Exception:
                continue
        self._catalog = catalog
        self._loaded = True

    def match(self, user_text: str) -> dict | None:
        """
        Return the best matching skill entry, or None.
        Uses word-overlap scoring then Haiku for disambiguation
        when multiple skills are close in score.
        """
        if not self._loaded or len(user_text) < MIN_MSG_LEN:
            return None

        query_tokens = _tokenize(user_text)
        if not query_tokens:
            return None

        # Score every skill by token overlap
        scored = []
        for entry in self._catalog:
            overlap = len(query_tokens & entry["tokens"])
            if overlap >= SCORE_THRESHOLD:
                scored.append((overlap, entry))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        top_score, top_entry = scored[0]

        # If there's a clear winner (score ≥ 2× second place), use it directly
        if len(scored) == 1 or top_score >= scored[1][0] * 2:
            return top_entry

        # Ambiguous — ask Haiku to pick from top 8 candidates
        candidates = scored[:8]
        lines = "\n".join(f"- {e['name']}: {e['description']}" for _, e in candidates)
        try:
            resp = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=60,
                system="You select the most relevant Claude Code skill for a user request.",
                messages=[{"role": "user", "content": (
                    f"User request: \"{user_text}\"\n\n"
                    f"Candidate skills:\n{lines}\n\n"
                    "Reply with the skill name that best matches, or NONE if none fit. "
                    "Reply with just the skill name, nothing else."
                )}],
            )
            chosen = next(
                (b.text.strip() for b in resp.content if hasattr(b, "text")), "NONE"
            )
            if chosen.upper() == "NONE":
                return None
            for _, entry in candidates:
                if entry["name"].lower() == chosen.lower():
                    return entry
        except Exception:
            pass

        return top_entry  # fallback to highest overlap

    def read_skill(self, entry: dict) -> str:
        """Read the full SKILL.md content for injection into the brain call."""
        try:
            return entry["path"].read_text(errors="ignore")
        except Exception:
            return ""

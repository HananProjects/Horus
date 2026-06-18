import json
import re
import subprocess
import anthropic
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from ddgs import DDGS
import nodes as node_store
import profile as user_profile
import agents as agent_registry
import gmail as gmail_module

import os
load_dotenv(Path(__file__).parent / ".env", override=True)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def _build_maps_url(inp: dict) -> str:
    key = GOOGLE_MAPS_API_KEY
    mode = inp.get("map_mode", "place")
    base = "https://www.google.com/maps/embed/v1"
    if mode == "directions":
        origin = inp.get("origin", "")
        dest = inp.get("destination", inp.get("location", ""))
        return f"{base}/directions?key={key}&origin={origin}&destination={dest}&mode=driving"
    if mode == "search":
        q = inp.get("location", inp.get("title", ""))
        return f"{base}/search?key={key}&q={q}"
    if mode == "satellite":
        q = inp.get("location", inp.get("title", ""))
        zoom = inp.get("zoom", 15)
        return f"{base}/place?key={key}&q={q}&maptype=satellite&zoom={zoom}"
    # default: place — zoom 16 is neighbourhood level, good starting point
    q = inp.get("location", inp.get("title", ""))
    zoom = inp.get("zoom", 16)
    return f"{base}/place?key={key}&q={q}&maptype=satellite&zoom={zoom}"


# ── helper data fetchers ────────────────────────────────────────────────────

def _fetch_stock_data(symbol: str) -> dict:
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params={"interval": "1d", "range": "1mo"}, headers=headers, timeout=10)
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        meta = res["meta"]
        closes = [c for c in (res["indicators"]["quote"][0].get("close") or []) if c is not None]
        price = meta.get("regularMarketPrice") or meta.get("price", 0)
        prev = meta.get("previousClose") or meta.get("chartPreviousClose", price)
        change = round(price - prev, 2)
        pct = round((change / prev * 100) if prev else 0, 2)
        return {
            "price": round(price, 2), "change": change, "pct": pct,
            "currency": meta.get("currency", "USD"),
            "exchange": meta.get("exchangeName", ""),
            "closes": closes[-30:],
        }
    except Exception as e:
        return {"error": str(e)}


def _fetch_sports_score(query: str) -> dict:
    try:
        import requests
        leagues = [
            ("basketball", "nba"), ("football", "nfl"), ("baseball", "mlb"),
            ("hockey", "nhl"), ("basketball", "mens-college-basketball"),
        ]
        query_lower = query.lower()
        headers = {"User-Agent": "Mozilla/5.0"}
        for sport, league in leagues:
            try:
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code != 200:
                    continue
                data = r.json()
                for event in data.get("events", []):
                    name = event.get("name", "").lower()
                    short_name = event.get("shortName", "").lower()
                    words = [w for w in query_lower.split() if len(w) > 2]
                    if not any(w in name or w in short_name for w in words):
                        continue
                    comp = event["competitions"][0]
                    competitors = comp["competitors"]
                    home = next((c for c in competitors if c["homeAway"] == "home"), competitors[0])
                    away = next((c for c in competitors if c["homeAway"] == "away"), competitors[-1])
                    status = event["status"]
                    state = status["type"]["state"]
                    series_note = ""
                    notes = comp.get("notes", [])
                    if notes:
                        series_note = notes[0].get("headline", "")
                    return {
                        "game_id": event["id"], "sport": sport, "league": league,
                        "title": event.get("name", ""),
                        "home_team": {
                            "name": home["team"]["displayName"],
                            "abbrev": home["team"]["abbreviation"],
                            "logo": home["team"].get("logo", ""),
                            "score": home.get("score", "0"),
                            "record": home.get("records", [{}])[0].get("summary", "") if home.get("records") else "",
                        },
                        "away_team": {
                            "name": away["team"]["displayName"],
                            "abbrev": away["team"]["abbreviation"],
                            "logo": away["team"].get("logo", ""),
                            "score": away.get("score", "0"),
                            "record": away.get("records", [{}])[0].get("summary", "") if away.get("records") else "",
                        },
                        "status": "live" if state == "in" else ("final" if state == "post" else "upcoming"),
                        "status_display": status.get("displayClock", "") if state == "in" else status["type"].get("description", ""),
                        "period": status.get("period", 0),
                        "series_summary": series_note,
                    }
            except Exception:
                continue
        return {"error": f"No current game found for '{query}'"}
    except Exception as e:
        return {"error": str(e)}


# ── system prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Horus, a personal AI assistant who speaks directly to the user out loud. Your responses are converted to speech, so write exactly as you would speak — natural, clear, and conversational. Never use markdown formatting: no asterisks, no bullet points, no headers, no symbols. Just plain spoken sentences.

Be warm, direct, and human. Get to the point without unnecessary filler. You have tools — use them. Search the web for anything current. Read, write, and manage files when asked. Open apps and files. You have full access to Hanan's Mac.

You have three specialized agents you can delegate heavy work to using delegate_to_agent:
- research: Deep web research, fact-finding, news, prices, current events.
- code: Writing, editing, debugging, and running code or scripts. Has full file system access.
- task: Creating reminders, schedules, and to-do organization.

You can call delegate_to_agent multiple times in one response — they run in parallel automatically. Synthesize agent results into a single spoken response.

The visual interface has a central glowing sphere called "the eye". Workspace nodes branch off it representing things being tracked or worked on. When Hanan says "add this to the eye" or "put that on the eye", use add_workspace_node. When he says "remove that from the eye", use remove_workspace_node.

Use visual display tools aggressively. Any time Hanan asks about something visual, show it on the eye without being asked. For stocks use show_visual with content_type="stock". For people, places, products — call image_search then show_visual with content_type="image". For YouTube use content_type="video". For live sports use content_type="score". For any location, place, address, travel, or geography question — use content_type="map". Use map_mode="directions" for routes, map_mode="search" for finding nearby places, map_mode="satellite" for overhead/3D views, map_mode="place" for a specific location. Never just describe something visual when you can show it.

You have full Gmail access. Use gmail_search to find emails, gmail_read to read them, gmail_trash to delete, gmail_bulk_trash to clean categories, gmail_send to compose. Always search first and confirm count before bulk-trashing.

You have access to Hanan's Obsidian knowledge vault. When relevant notes are provided below, use them to give informed, personalized answers.

You are constantly learning about Hanan. Whenever a conversation reveals something meaningful — a preference, a habit, a goal, a project — call update_user_profile immediately. Be specific. Over time this makes you genuinely tailored to him.

You have access to Hanan's NaniStack agency dashboard. Use nanistack_dashboard to get live data on clients, requests, todos, and revenue. Query it any time Hanan asks about his agency, clients, tasks, income, or pending work.

You have autonomous self-improvement capabilities that are already running:
- Every 6 hours, a background learning daemon runs (even when the app is closed) that scans your wiki for knowledge gaps, researches them via web search, discovers new Claude Code skills on GitHub, and reviews and installs safe ones automatically.
- After every conversation turn, a background Haiku call compiles what was discussed into structured wiki pages in Obsidian (Hanan Profile, Job Search, Technical Skills, Personal Life, Horus Project).
- A self-coder reviews discoveries and proposes safe code improvements to your own backend, which are applied and git-committed automatically after passing heuristic and LLM safety review.
- On startup you summarize what you learned while Hanan was away.
These are not planned features — they are live and running right now."""

TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current, real-time information — weather, news, sports, prices, anything live.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file on the user's Mac.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file on the user's Mac.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    },
    {
        "name": "list_directory",
        "description": "List files and folders inside a directory.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "run_command",
        "description": "Run a shell command on the user's Mac and return the output.",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "open_path",
        "description": "Open a file, folder, or application on the user's Mac.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "add_workspace_node",
        "description": "Add a project or topic node to the visual workspace sphere.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "node_type": {"type": "string", "enum": ["pdf", "url", "image", "file", "app", "task", "note", "music", "search", "generic"]},
                "metadata": {"type": "object"},
            },
            "required": ["label"],
        },
    },
    {
        "name": "remove_workspace_node",
        "description": "Remove a node from the visual workspace sphere.",
        "input_schema": {"type": "object", "properties": {"node_id": {"type": "integer"}}, "required": ["node_id"]},
    },
    {
        "name": "update_user_profile",
        "description": "Store something learned about Hanan — preferences, habits, goals, projects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["preferences", "habits", "goals", "dislikes", "projects", "facts", "communication"]},
                "item": {"type": "string"},
            },
            "required": ["category", "item"],
        },
    },
    {
        "name": "image_search",
        "description": "Search for images and return direct image URLs.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "show_visual",
        "description": "Display rich visual content on the eye. Use for stocks, images, videos, webpages, sports scores, and maps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content_type": {
                    "type": "string",
                    "enum": ["stock", "image", "video", "webpage", "score", "map"],
                    "description": "map: Google Maps/Earth view. Use for any location, place, directions, or satellite imagery request.",
                },
                "title": {"type": "string"},
                "symbol": {"type": "string"},
                "url": {"type": "string"},
                "query": {"type": "string"},
                "location": {"type": "string", "description": "For map: place name or address, e.g. 'Eiffel Tower, Paris' or 'Saskatoon, SK'"},
                "map_mode": {
                    "type": "string",
                    "enum": ["place", "satellite", "search", "directions"],
                    "description": "place: show a specific location. satellite: overhead/3D satellite view. search: search for places. directions: route between two points.",
                },
                "origin": {"type": "string", "description": "For directions mode: starting location"},
                "destination": {"type": "string", "description": "For directions mode: destination location"},
            },
            "required": ["content_type", "title"],
        },
    },
    {
        "name": "gmail_search",
        "description": "Search Gmail. Supports full Gmail query syntax.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]},
    },
    {
        "name": "gmail_read",
        "description": "Read the full body of a specific email by ID.",
        "input_schema": {"type": "object", "properties": {"message_id": {"type": "string"}}, "required": ["message_id"]},
    },
    {
        "name": "gmail_trash",
        "description": "Move specific emails to trash by their IDs.",
        "input_schema": {"type": "object", "properties": {"message_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["message_ids"]},
    },
    {
        "name": "gmail_bulk_trash",
        "description": "Move ALL emails matching a query to trash.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]},
    },
    {
        "name": "gmail_send",
        "description": "Send an email.",
        "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "thread_id": {"type": "string"}}, "required": ["to", "subject", "body"]},
    },
    {
        "name": "delegate_to_agent",
        "description": "Delegate a subtask to a specialized agent. Call multiple times to run agents in parallel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "enum": ["research", "code", "task"]},
                "task": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["agent", "task"],
        },
    },
    {
        "name": "nanistack_dashboard",
        "description": "Read live data from the NaniStack agency dashboard — clients, task requests, todos, and revenue stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["all", "companies", "requests", "todos", "stats"],
                    "description": "Which section to retrieve. Use 'all' for a full overview.",
                },
            },
            "required": ["section"],
        },
    },
]

# OpenAI-compatible tool format for Ollama
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]


# ── tool implementations ────────────────────────────────────────────────────

def _image_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=6))
        parts = [
            f"Title: {r.get('title', '')}\nImage URL: {r.get('image', '')}\nSource: {r.get('url', '')}"
            for r in results if r.get("image")
        ]
        return "\n\n".join(parts) if parts else "No usable image URLs found."
    except Exception as e:
        return f"Image search failed: {e}"


def _web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        parts = [f"{r['title']}\n{r['body']}\nSource: {r['href']}" for r in results]
        return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search failed: {e}"


def _read_file(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"File not found: {path}"
        if p.stat().st_size > 100_000:
            return f"File too large. Use run_command to read a portion."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written successfully to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def _list_directory(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Path not found: {path}"
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = [("[DIR] " if e.is_dir() else "[FILE] ") + e.name for e in entries[:100]]
        return "\n".join(lines) or "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


def _run_command(command: str) -> str:
    try:
        result = subprocess.run(
            ["zsh", "-c", command],
            capture_output=True, text=True, timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:4000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"


def _open_path(path: str) -> str:
    try:
        subprocess.Popen(["open", path])
        return f"Opened: {path}"
    except Exception as e:
        return f"Could not open '{path}': {e}"


def _add_node(label: str, node_type: str = "generic", metadata: dict = None) -> str:
    nodes = node_store.add(label, node_type, metadata or {})
    return f"Node '{label}' ({node_type}) added. Current nodes: {[n['label'] for n in nodes]}"


def _remove_node(node_id: int) -> str:
    nodes = node_store.remove(node_id)
    return f"Node removed. Current nodes: {[n['label'] for n in nodes]}"


_NANISTACK_DATA = Path("B:/NaniStack/data")

def _nanistack_dashboard(section: str = "all") -> str:
    try:
        def _load(name: str):
            p = _NANISTACK_DATA / f"{name}.json"
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

        need_companies = section in ("all", "companies", "stats")
        need_requests  = section in ("all", "requests",  "stats")
        need_todos     = section in ("all", "todos")

        companies = _load("companies") if need_companies else []
        requests  = _load("requests")  if need_requests  else []
        todos     = _load("todos")     if need_todos     else []

        out: dict = {}
        if need_companies:
            out["companies"] = companies
        if need_requests:
            out["recent_requests"] = requests[:15]
        if need_todos:
            out["todos"] = todos
        if section in ("all", "stats"):
            mrr = sum(c.get("mrr", 0) for c in companies)
            open_reqs = [r for r in requests if r.get("status") in ("pending", "in_progress")]
            out["stats"] = {
                "companies": len(companies),
                "totalRequests": len(requests),
                "openRequests": len(open_reqs),
                "monthlyRevenue": f"${mrr:,}",
            }

        return json.dumps(out, indent=2)
    except Exception as e:
        return f"Error reading NaniStack dashboard: {e}"


TOOL_HANDLERS = {
    "web_search": lambda inp: _web_search(inp["query"]),
    "image_search": lambda inp: _image_search(inp["query"]),
    "read_file": lambda inp: _read_file(inp["path"]),
    "write_file": lambda inp: _write_file(inp["path"], inp["content"]),
    "list_directory": lambda inp: _list_directory(inp["path"]),
    "run_command": lambda inp: _run_command(inp["command"]),
    "open_path": lambda inp: _open_path(inp["path"]),
    "add_workspace_node": lambda inp: _add_node(inp["label"], inp.get("node_type", "generic"), inp.get("metadata")),
    "remove_workspace_node": lambda inp: _remove_node(inp["node_id"]),
    "update_user_profile": lambda inp: user_profile.add_item(inp["category"], inp["item"]),
    "gmail_search": lambda inp: str(gmail_module.search_emails(inp["query"], min(inp.get("max_results", 25), 50))),
    "gmail_read": lambda inp: str(gmail_module.read_email(inp["message_id"])),
    "gmail_trash": lambda inp: gmail_module.trash_emails(inp["message_ids"]),
    "gmail_bulk_trash": lambda inp: gmail_module.bulk_trash(inp["query"], inp.get("max_results", 500)),
    "gmail_send": lambda inp: gmail_module.send_email(inp["to"], inp["subject"], inp["body"], inp.get("thread_id")),
    "nanistack_dashboard": lambda inp: _nanistack_dashboard(inp.get("section", "all")),
}


def _handle_visual_tool(inp: dict) -> tuple:
    """Build panel_data and result string for a show_visual tool call."""
    panel_data = {
        "panel_type": "visual",
        "content_type": inp["content_type"],
        "title": inp["title"],
    }
    if inp["content_type"] == "stock" and inp.get("symbol"):
        panel_data["symbol"] = inp["symbol"].upper()
        panel_data["data"] = _fetch_stock_data(inp["symbol"].upper())
    elif inp["content_type"] == "score":
        query = inp.get("query") or inp.get("title", "")
        score_data = _fetch_sports_score(query)
        panel_data["data"] = score_data
        panel_data["game_id"] = score_data.get("game_id", "")
        panel_data["sport"] = score_data.get("sport", "basketball")
        panel_data["league"] = score_data.get("league", "nba")
    elif inp["content_type"] == "video" and inp.get("url"):
        url = inp["url"]
        if "youtube.com/watch" in url:
            vid_id = url.split("v=")[-1].split("&")[0]
            url = f"https://www.youtube.com/embed/{vid_id}?autoplay=0"
        elif "youtu.be/" in url:
            vid_id = url.split("youtu.be/")[-1].split("?")[0]
            url = f"https://www.youtube.com/embed/{vid_id}?autoplay=0"
        panel_data["url"] = url
    elif inp["content_type"] == "map":
        panel_data["url"] = _build_maps_url(inp)
        panel_data["api_key"] = GOOGLE_MAPS_API_KEY
        panel_data["map_mode"] = inp.get("map_mode", "place")
        panel_data["location"] = inp.get("location") or inp.get("destination") or inp.get("title", "")
        if inp.get("origin"):
            panel_data["origin"] = inp["origin"]
        if inp.get("destination"):
            panel_data["destination"] = inp["destination"]
    elif inp.get("url"):
        panel_data["url"] = inp["url"]
    return panel_data, f"Visual displayed: {inp['content_type']} — '{inp['title']}'."


# ── Brain ──────────────────────────────────────────────────────────────────

class Brain:
    def __init__(self):
        self.client = anthropic.Anthropic(timeout=30.0)
        self.model = "claude-haiku-4-5-20251001"
        self.provider: str = os.getenv("HORUS_PROVIDER", "claude")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:14b")
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self._ollama_client = None
        self.history: list[dict] = []

    def set_provider(self, provider: str) -> None:
        if provider not in ("claude", "ollama"):
            raise ValueError(f"Unknown provider: {provider!r}")
        self.provider = provider

    def _get_ollama_client(self):
        if self._ollama_client is None:
            try:
                from openai import OpenAI as _OllamaClient
            except ImportError:
                raise RuntimeError("openai package not installed — run: pip install openai")
            self._ollama_client = _OllamaClient(
                base_url=self.ollama_base_url,
                api_key="ollama",
            )
        return self._ollama_client

    def _build_system(
        self,
        memories: Optional[list],
        obsidian_notes: Optional[list],
        graph_context: Optional[str],
    ) -> str:
        memory_block = ""
        if memories:
            memory_block = "\n\n[Relevant memories from past conversations]\n" + "\n".join(f"- {m}" for m in memories)
        obsidian_block = ""
        if obsidian_notes:
            parts = [f"**{n['title']}** ({n['path']}):\n{n['snippet']}" for n in obsidian_notes]
            obsidian_block = "\n\n[Relevant notes from Obsidian vault]\n" + "\n\n".join(parts)
        graph_block = ""
        if graph_context:
            graph_block = f"\n\n[Knowledge graph context — token-compressed from codebase]\n{graph_context}"
        profile = user_profile.load()
        profile_block = user_profile.to_prompt_block(profile)
        system = SYSTEM_PROMPT
        if profile_block:
            system += f"\n\n{profile_block}"
        system += memory_block + obsidian_block + graph_block
        return system

    def chat(
        self,
        user_text: str,
        memories: Optional[list] = None,
        obsidian_notes: Optional[list] = None,
        graph_context: Optional[str] = None,
        on_token=None,
    ) -> tuple[str, list]:
        if self.provider == "ollama":
            return self._chat_ollama(user_text, memories, obsidian_notes, graph_context, on_token=on_token)
        return self._chat_claude(user_text, memories, obsidian_notes, graph_context, on_token=on_token)

    def _chat_claude(
        self,
        user_text: str,
        memories: Optional[list] = None,
        obsidian_notes: Optional[list] = None,
        graph_context: Optional[str] = None,
        on_token=None,
    ) -> tuple[str, list]:
        system = self._build_system(memories, obsidian_notes, graph_context)
        self.history.append({"role": "user", "content": user_text})
        messages = list(self.history)
        panels: list[dict] = []
        iterations = 0
        response = None

        while iterations < 12:
            got_text = False
            with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    if not got_text:
                        got_text = True
                        if on_token:
                            on_token("__start__")
                    if on_token:
                        on_token(text)
                if on_token:
                    on_token("__done__" if got_text else "__cancel__")
                response = stream.get_final_message()

            iterations += 1

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_blocks = [b for b in response.content if b.type == "tool_use"]

                # Run delegate_to_agent calls in parallel
                agent_blocks = [b for b in tool_blocks if b.name == "delegate_to_agent"]
                agent_results: dict[str, str] = {}
                if agent_blocks:
                    with ThreadPoolExecutor(max_workers=len(agent_blocks)) as ex:
                        future_to_id = {
                            ex.submit(
                                agent_registry.run_agent,
                                b.input["agent"],
                                b.input["task"],
                                b.input.get("context", ""),
                            ): b.id
                            for b in agent_blocks
                        }
                        for future in as_completed(future_to_id):
                            agent_results[future_to_id[future]] = future.result()

                    for block in agent_blocks:
                        panels.append({
                            "panel_type": block.input["agent"],
                            "title": block.input["task"][:60],
                            "content": agent_results.get(block.id, ""),
                        })

                tool_results = []
                for block in tool_blocks:
                    if block.name == "delegate_to_agent":
                        result = agent_results.get(block.id, "[agent returned no result]")
                    elif block.name == "show_visual":
                        panel_data, result = _handle_visual_tool(block.input)
                        panels.append(panel_data)
                    else:
                        handler = TOOL_HANDLERS.get(block.name)
                        result = handler(block.input) if handler else f"Unknown tool: {block.name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        reply = next(
            (block.text for block in response.content if hasattr(block, "text")),
            "Sorry, I ran into an issue. Try again.",
        )
        self.history.append({"role": "assistant", "content": reply})
        if len(self.history) > 40:
            self.history = self.history[-40:]
        return reply, panels

    def _stream_ollama_once(self, client, messages, on_token=None):
        """Single streaming Ollama call.

        on_token protocol (called from the calling thread):
          "__start__"  — a text response is beginning (not a tool call)
          str chunk    — text token
          "__done__"   — text stream finished (final response)
          "__cancel__" — this turn was a tool call, not text
        """
        stream = client.chat.completions.create(
            model=self.ollama_model,
            messages=messages,
            tools=OLLAMA_TOOLS,
            stream=True,
            max_tokens=512,
        )

        full_text = ""
        tool_calls_acc: dict[int, dict] = {}
        finish_reason = None
        is_text: Optional[bool] = None

        for chunk in stream:
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta

            if delta.content:
                full_text += delta.content
                if is_text is None:
                    is_text = True
                    if on_token:
                        on_token("__start__")
                if on_token:
                    on_token(delta.content)

            if delta.tool_calls:
                if is_text is None:
                    is_text = False
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

        if on_token:
            on_token("__done__" if is_text else "__cancel__")

        tool_calls_list = [
            {
                "id": tool_calls_acc[i]["id"],
                "type": "function",
                "function": {
                    "name": tool_calls_acc[i]["name"],
                    "arguments": tool_calls_acc[i]["arguments"],
                },
            }
            for i in sorted(tool_calls_acc.keys())
        ]
        return full_text, tool_calls_list, finish_reason

    def _chat_ollama(
        self,
        user_text: str,
        memories: Optional[list] = None,
        obsidian_notes: Optional[list] = None,
        graph_context: Optional[str] = None,
        on_token=None,
    ) -> tuple[str, list]:
        system = self._build_system(memories, obsidian_notes, graph_context)
        system += "\n/no_think"

        self.history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": system}] + list(self.history)
        panels: list[dict] = []
        iterations = 0
        client = self._get_ollama_client()
        full_text = ""

        while iterations < 12:
            full_text, tool_calls_list, finish_reason = self._stream_ollama_once(
                client, messages, on_token=on_token
            )
            iterations += 1

            if finish_reason == "tool_calls":
                messages.append({
                    "role": "assistant",
                    "content": full_text or "",
                    "tool_calls": tool_calls_list,
                })

                agent_blocks = [tc for tc in tool_calls_list if tc["function"]["name"] == "delegate_to_agent"]
                agent_results: dict[str, str] = {}
                if agent_blocks:
                    with ThreadPoolExecutor(max_workers=len(agent_blocks)) as ex:
                        future_to_id: dict = {}
                        for tc in agent_blocks:
                            inp = json.loads(tc["function"]["arguments"])
                            f = ex.submit(
                                agent_registry.run_agent,
                                inp["agent"], inp["task"], inp.get("context", ""),
                            )
                            future_to_id[f] = tc["id"]
                        for future in as_completed(future_to_id):
                            agent_results[future_to_id[future]] = future.result()

                    for tc in agent_blocks:
                        inp = json.loads(tc["function"]["arguments"])
                        panels.append({
                            "panel_type": inp["agent"],
                            "title": inp["task"][:60],
                            "content": agent_results.get(tc["id"], ""),
                        })

                for tc in tool_calls_list:
                    name = tc["function"]["name"]
                    inp = json.loads(tc["function"]["arguments"])

                    if name == "delegate_to_agent":
                        result = agent_results.get(tc["id"], "[agent returned no result]")
                    elif name == "show_visual":
                        panel_data, result = _handle_visual_tool(inp)
                        panels.append(panel_data)
                    else:
                        handler = TOOL_HANDLERS.get(name)
                        result = handler(inp) if handler else f"Unknown tool: {name}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(result),
                    })
            else:
                break

        raw = full_text or "Sorry, I ran into an issue."
        reply = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip() or raw.strip()

        self.history.append({"role": "assistant", "content": reply})
        if len(self.history) > 40:
            self.history = self.history[-40:]
        return reply, panels

    def reset(self):
        self.history = []

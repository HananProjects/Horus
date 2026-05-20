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

load_dotenv(Path(__file__).parent / ".env")


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

Use visual display tools aggressively. Any time Hanan asks about something visual, show it on the eye without being asked. For stocks use show_visual with content_type="stock". For people, places, products — call image_search then show_visual with content_type="image". For YouTube use content_type="video". For live sports use content_type="score". Never just describe something visual when you can show it.

You have full Gmail access. Use gmail_search to find emails, gmail_read to read them, gmail_trash to delete, gmail_bulk_trash to clean categories, gmail_send to compose. Always search first and confirm count before bulk-trashing.

You have access to Hanan's Obsidian knowledge vault. When relevant notes are provided below, use them to give informed, personalized answers.

You are constantly learning about Hanan. Whenever a conversation reveals something meaningful — a preference, a habit, a goal, a project — call update_user_profile immediately. Be specific. Over time this makes you genuinely tailored to him."""

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
        "description": "Display rich visual content on the eye. Use for stocks, images, videos, webpages, sports scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content_type": {"type": "string", "enum": ["stock", "image", "video", "webpage", "score"]},
                "title": {"type": "string"},
                "symbol": {"type": "string"},
                "url": {"type": "string"},
                "query": {"type": "string"},
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
}


# ── Brain ──────────────────────────────────────────────────────────────────

class Brain:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-6"
        self.history: list[dict] = []

    def chat(
        self,
        user_text: str,
        memories: Optional[list] = None,
        obsidian_notes: Optional[list] = None,
        graph_context: Optional[str] = None,
    ) -> tuple[str, list]:
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

        self.history.append({"role": "user", "content": user_text})
        messages = list(self.history)
        panels: list[dict] = []
        iterations = 0

        while iterations < 12:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=TOOLS,
                messages=messages,
            )
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
                        inp = block.input
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
                        elif inp.get("url"):
                            panel_data["url"] = inp["url"]
                        panels.append(panel_data)
                        result = f"Visual displayed: {inp['content_type']} — '{inp['title']}'."
                    else:
                        handler = TOOL_HANDLERS.get(block.name)
                        result = handler(block.input) if handler else f"Unknown tool: {block.name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
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

    def reset(self):
        self.history = []

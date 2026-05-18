import os
import subprocess
import anthropic
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from ddgs import DDGS
import nodes as node_store

load_dotenv(Path(__file__).parent / ".env")

SYSTEM_PROMPT = """You are Horus, a personal AI assistant who speaks directly to the user out loud. Your responses are converted to speech, so write exactly as you would speak — natural, clear, and conversational. Never use markdown formatting: no asterisks, no bullet points, no headers, no symbols. Just plain spoken sentences.

Be warm, direct, and human. Get to the point without unnecessary filler. You have tools — use them. Search the web for anything current. Read, write, and manage files when asked. Run commands when needed. Open apps and files. You have full access to Hanan's Windows PC.

The visual interface has a central glowing sphere called "the eye". Workspace nodes branch off it representing things being tracked or worked on. When Hanan says "add this to the eye" or "put that on the eye", use add_workspace_node. When he says "remove that from the eye" or "take that off the eye", use remove_workspace_node.

The user's name is Hanan. He is a Computer Engineering graduate, currently job hunting in tech and building personal projects for his portfolio."""

TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current, real-time information — weather, news, sports, prices, anything live.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file on the user's PC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file on the user's PC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to write to"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders inside a directory on the user's PC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a PowerShell command on the user's Windows PC and return the output. Use this for system tasks, file operations, or anything shell-related.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "PowerShell command to execute"}
            },
            "required": ["command"],
        },
    },
    {
        "name": "open_path",
        "description": "Open a file, folder, or application on the user's Windows PC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, folder path, or application name to open"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "add_workspace_node",
        "description": "Add a project or topic node to the visual workspace sphere. Use this when the user starts working on something new, mentions an ongoing project, or asks you to track something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Short label for the node, 2-4 words max"}
            },
            "required": ["label"],
        },
    },
    {
        "name": "remove_workspace_node",
        "description": "Remove a node from the visual workspace sphere when a project is done or the user wants it removed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "integer", "description": "ID of the node to remove"}
            },
            "required": ["node_id"],
        },
    },
]


# --- Tool implementations ---

def _web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No results found."
        parts = [f"{r['title']}\n{r['body']}\nSource: {r['href']}" for r in results]
        return "\n\n".join(parts)
    except Exception as e:
        return f"Search failed: {e}"


def _read_file(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"File not found: {path}"
        if p.stat().st_size > 100_000:
            return f"File too large ({p.stat().st_size} bytes). Use run_command to read a specific portion."
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
        if sum(1 for _ in p.iterdir()) > 100:
            lines.append("... (showing first 100 entries)")
        return "\n".join(lines) or "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


def _run_command(command: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
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
        os.startfile(path)
        return f"Opened: {path}"
    except Exception as e:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", path])
            return f"Opened: {path}"
        except Exception:
            return f"Could not open '{path}': {e}"


def _add_node(label: str) -> str:
    nodes = node_store.add(label)
    return f"Node '{label}' added. Current nodes: {[n['label'] for n in nodes]}"


def _remove_node(node_id: int) -> str:
    nodes = node_store.remove(node_id)
    return f"Node removed. Current nodes: {[n['label'] for n in nodes]}"


TOOL_HANDLERS = {
    "web_search": lambda inp: _web_search(inp["query"]),
    "read_file": lambda inp: _read_file(inp["path"]),
    "write_file": lambda inp: _write_file(inp["path"], inp["content"]),
    "list_directory": lambda inp: _list_directory(inp["path"]),
    "run_command": lambda inp: _run_command(inp["command"]),
    "open_path": lambda inp: _open_path(inp["path"]),
    "add_workspace_node": lambda inp: _add_node(inp["label"]),
    "remove_workspace_node": lambda inp: _remove_node(inp["node_id"]),
}


class Brain:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-6"
        self.history: list[dict] = []

    def chat(self, user_text: str, memories: Optional[list] = None) -> str:
        memory_block = ""
        if memories:
            memory_block = "\n\n[Relevant memories]\n" + "\n".join(f"- {m}" for m in memories)

        system = SYSTEM_PROMPT + memory_block
        self.history.append({"role": "user", "content": user_text})

        messages = list(self.history)
        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
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
            "I couldn't generate a response."
        )

        self.history.append({"role": "assistant", "content": reply})
        if len(self.history) > 40:
            self.history = self.history[-40:]

        return reply

    def reset(self):
        self.history = []

import subprocess
import anthropic
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from ddgs import DDGS


# --- Shared tool implementations ---

def _search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No results found."
        return "\n\n".join(f"{r['title']}\n{r['body']}\nSource: {r['href']}" for r in results)
    except Exception as e:
        return f"Search failed: {e}"


def _read(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"File not found: {path}"
        if p.stat().st_size > 100_000:
            return f"File too large. Use run_command to read a portion."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


def _write(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def _listdir(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Path not found: {path}"
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        return "\n".join(("[DIR] " if e.is_dir() else "[FILE] ") + e.name for e in entries[:100])
    except Exception as e:
        return f"Error listing directory: {e}"


def _shell(command: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True, text=True, timeout=30,
        )
        return (result.stdout + result.stderr).strip()[:4000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"


# --- Base agent ---

class _Agent:
    def __init__(self, name: str, system: str, tools: list, model: str):
        self.name = name
        self.system = system
        self.tools = tools
        self.model = model
        self.client = anthropic.Anthropic()

    def run(self, task: str, context: str = "") -> str:
        content = f"Context: {context}\n\nTask: {task}" if context else task
        messages = [{"role": "user", "content": content}]

        while True:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system,
                tools=self.tools,
                messages=messages,
            )
            if resp.stop_reason != "tool_use":
                break
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = self._dispatch(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            messages.append({"role": "user", "content": results})

        return next(
            (b.text for b in resp.content if hasattr(b, "text")),
            f"[{self.name} agent] No result generated."
        )

    def _dispatch(self, name: str, inp: dict) -> str:
        return f"Unknown tool: {name}"


# --- Specialized agents ---

class _ResearchAgent(_Agent):
    _TOOLS = [
        {
            "name": "web_search",
            "description": "Search the web for current information.",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    ]

    def __init__(self):
        super().__init__(
            name="research",
            system=(
                "You are a research specialist. Your job is to find accurate, up-to-date information. "
                "Search the web thoroughly — run multiple searches if needed to get a complete picture. "
                "Synthesize findings into a clear, factual summary with sources. Plain text only, no markdown."
            ),
            tools=self._TOOLS,
            model="claude-haiku-4-5-20251001",
        )

    def _dispatch(self, name: str, inp: dict) -> str:
        if name == "web_search":
            return _search(inp["query"])
        return super()._dispatch(name, inp)


class _CodeAgent(_Agent):
    _TOOLS = [
        {
            "name": "read_file",
            "description": "Read a file on the system.",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
        {
            "name": "write_file",
            "description": "Write or overwrite a file.",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        },
        {
            "name": "run_command",
            "description": "Run a PowerShell command and return output.",
            "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        },
        {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    ]

    def __init__(self):
        super().__init__(
            name="code",
            system=(
                "You are a coding specialist with full access to the file system. "
                "Write clean, working code. Debug issues methodically. Run commands to verify your work. "
                "Always check existing code before writing new code. Return a clear summary of what you did."
            ),
            tools=self._TOOLS,
            model="claude-sonnet-4-6",
        )

    def _dispatch(self, name: str, inp: dict) -> str:
        if name == "read_file":      return _read(inp["path"])
        if name == "write_file":     return _write(inp["path"], inp["content"])
        if name == "run_command":    return _shell(inp["command"])
        if name == "list_directory": return _listdir(inp["path"])
        return super()._dispatch(name, inp)


class _TaskAgent(_Agent):
    _TOOLS = [
        {
            "name": "run_command",
            "description": "Run a PowerShell command to create reminders or scheduled tasks.",
            "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        },
    ]

    def __init__(self):
        super().__init__(
            name="task",
            system=(
                "You are a task and scheduling specialist. Organize work, set reminders, and manage to-dos. "
                "Use Windows Task Scheduler via PowerShell to create actual scheduled reminders when asked. "
                "Return a clear plain-text summary of what was set up."
            ),
            tools=self._TOOLS,
            model="claude-haiku-4-5-20251001",
        )

    def _dispatch(self, name: str, inp: dict) -> str:
        if name == "run_command":
            return _shell(inp["command"])
        return super()._dispatch(name, inp)


# --- Registry and public API ---

_REGISTRY: dict[str, _Agent] = {
    "research": _ResearchAgent(),
    "code":     _CodeAgent(),
    "task":     _TaskAgent(),
}

AGENT_NAMES = list(_REGISTRY.keys())


def run_agent(agent_name: str, task: str, context: str = "") -> str:
    agent = _REGISTRY.get(agent_name)
    if not agent:
        return f"No agent named '{agent_name}'. Available: {AGENT_NAMES}"
    print(f"[agent:{agent_name}] {task[:80]}")
    result = agent.run(task, context)
    print(f"[agent:{agent_name}] done.")
    return result


def run_parallel(calls: list[dict]) -> list[str]:
    """Run multiple agent calls concurrently. Each call: {agent, task, context?}"""
    if len(calls) == 1:
        c = calls[0]
        return [run_agent(c["agent"], c["task"], c.get("context", ""))]
    with ThreadPoolExecutor(max_workers=len(calls)) as ex:
        future_to_idx = {
            ex.submit(run_agent, c["agent"], c["task"], c.get("context", "")): i
            for i, c in enumerate(calls)
        }
        results = [""] * len(calls)
        for future in as_completed(future_to_idx):
            results[future_to_idx[future]] = future.result()
        return results

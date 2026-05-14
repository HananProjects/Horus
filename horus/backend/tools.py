"""
Tool definitions for future Claude tool-use integration.
Currently a placeholder — wire these into brain.py when expanding capabilities.
"""

TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "open_app",
        "description": "Open an application on the user's Mac by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name, e.g. 'Spotify'"},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "remember",
        "description": "Explicitly store a fact in Horus's persistent memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact to remember"},
            },
            "required": ["fact"],
        },
    },
]

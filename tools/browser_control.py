from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "browser_control", "description": "Controls a browser session for explicit browser tasks. Use web_search for ordinary internet research. Use screen_control when the user asks to operate a browser window visible on the desktop. If a requested browser is unavailable, it selects an installed browser. When that browser is already running, ARGUS uses its own profile to avoid locking the user's active session; when it is closed, ARGUS can use its saved profile.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"}, "browser": {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the active ARGUS session or installed system default."}, "url": {"type": "STRING", "description": "URL for go_to / new_tab action"}, "query": {"type": "STRING", "description": "Search query for search action"}, "engine": {"type": "STRING", "description": "Search engine: duckduckgo (default) | google | bing | yandex"}, "selector": {"type": "STRING", "description": "CSS selector for click/type"}, "text": {"type": "STRING", "description": "Text to click or type"}, "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"}, "direction": {"type": "STRING", "description": "up | down for scroll"}, "amount": {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"}, "key": {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"}, "path": {"type": "STRING", "description": "Save path for screenshot"}, "incognito": {"type": "BOOLEAN", "description": "Open in private/incognito mode"}, "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"}}, "required": ["action"]}}

declaration["description"] += (
    " If a search engine presents an anti-robot verification, stop and report it; "
    "never interact with or bypass the challenge."
)


async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "browser_control", args)

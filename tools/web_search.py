from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "web_search", "description": "Searches through Gemini Google Search grounding and returns cited URLs. Use immediately for ordinary online searches. It makes no direct search-engine scraping requests and does not open a browser. If search fails, report the error; do not call another search tool automatically. Use screen_control only when the user specifically asks to search in or operate a visible browser.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "Search query"}, "mode": {"type": "STRING", "description": "search (default) or compare"}, "items": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"}, "aspect": {"type": "STRING", "description": "price | specs | reviews"}}, "required": ["query"]}}

async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "web_search", args)

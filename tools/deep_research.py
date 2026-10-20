from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "deep_research", "description": "Runs rigorous, multi-query web research and keeps the report in volatile memory unless the user asks to save it. Use when the user explicitly asks for deep, thorough, comprehensive, or source-backed research. On the first call, ask whether the user wants a background status bar or visible browser research. After completion, use this tool again to save the latest report or read it aloud.", "parameters": {"type": "OBJECT", "properties": {"question": {"type": "STRING", "description": "The research question. Required on the initial ask call; optional when confirming a pending request."}, "execution_mode": {"type": "STRING", "enum": ["ask", "background", "visible"], "description": "Always use ask initially. Background shows a labeled status bar; visible opens a controlled browser and visits sources."}, "result_action": {"type": "STRING", "enum": ["none", "save_files", "save_desktop", "read_report"], "description": "Action for the latest completed in-memory report. Use only after the user chooses one of these options."}, "depth": {"type": "STRING", "enum": ["quick", "standard", "deep"], "description": "Research breadth. Default: standard."}, "focus_areas": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Optional angles, constraints, or subtopics to prioritize."}, "max_sources": {"type": "INTEGER", "description": "Maximum verified source links to retain, from 5 to 50."}, "output_path": {"type": "STRING", "description": "Optional explicit path used only with save_files or save_desktop. Research never saves automatically."}}, "required": []}}

declaration["description"] += (
    " Search uses Gemini Google Search grounding and does not scrape DuckDuckGo/Bing "
    "or repeat queries through Google in a browser; visible mode opens only cited sources."
)


async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "deep_research", args)

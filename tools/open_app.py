from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "open_app", "description": "Opens an application or website on the computer. Use for a request to open something by itself. For a task that must continue inside the app, use screen_control with the complete task; it opens and focuses common requested apps before acting.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING", "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify') or website URL"}}, "required": ["app_name"]}}

async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "open_app", args)

"""Tool declaration for bounded visual screen control."""

from __future__ import annotations

from typing import Any


declaration: dict[str, Any] = {
    "name": "screen_control",
    "description": (
        "Inspect the focused desktop app or complete a multi-step task in its visible interface. "
        "Use action=inspect only when asked what is on screen. Use action=act for any requested on-screen interaction. "
        "It uses Windows accessibility controls first and visual targeting when needed, then verifies each step. "
        "Follow the user's explicit request without asking for per-click or per-message confirmation. "
        "Ask only if the target is genuinely ambiguous or if a file about to be shared appears to contain secrets or sensitive configuration."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["inspect", "act"], "description": "inspect describes the focused window; act completes the user's visible UI request."},
            "objective": {"type": "STRING", "description": "The complete user-authorized task, including app, target, and exact text if relevant."},
            "window_title": {"type": "STRING", "description": "Optional visible window title or app name to focus before acting."},
        },
        "required": ["action"],
    },
}


async def execute(ctx, args: dict[str, Any]) -> dict[str, Any]:
    from actions.screen_control import ScreenAgent
    from core.computer_control_preferences import load_direct_computer_control

    agent = ScreenAgent()
    action = str(args.get("action", "inspect") or "inspect").strip().lower()
    if action == "inspect":
        result = await __import__("asyncio").to_thread(agent.inspect)
        return {"result": result}
    if action != "act":
        return {"result": "Ação de tela desconhecida."}
    if not load_direct_computer_control():
        return {"result": "O controle direto do mouse e teclado está desativado em Configurações → Ações. Nenhuma ação foi executada."}
    result = await __import__("asyncio").to_thread(
        agent.run,
        str(args.get("objective", "") or ""),
        window_title=str(args.get("window_title", "") or ""),
    )
    return {"result": result.summary, "status": result.status, "steps_taken": result.steps_taken}

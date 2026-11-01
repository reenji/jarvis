"""Tool declaration for bounded visual screen control."""

from __future__ import annotations

import asyncio
from typing import Any


declaration: dict[str, Any] = {
    "name": "screen_control",
    "description": (
        "Inspect the focused desktop app or complete a multi-step task in its visible interface. "
        "Use action=inspect only when asked what is on screen. Use action=act for any requested on-screen interaction. "
        "If the requested app is not open, provide its name in window_title; if omitted, infer a common app named in the goal. ARGUS opens it, confirms focus, "
        "then uses Windows accessibility controls first and visual targeting when needed and verifies each step. "
        "Direct mouse and keyboard control is enabled by default. Complete clear requests without asking the user to click, select, or approve individual steps; choose the best matching visible result when the request identifies the target. "
        "Follow the user's explicit request without asking for per-click or per-message confirmation. "
        "Ask only if the target is genuinely ambiguous or if a file about to be shared appears to contain secrets or sensitive configuration."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["inspect", "act"], "description": "inspect describes the focused window; act completes the user's visible UI request."},
            "objective": {"type": "STRING", "description": "The complete user-authorized task, including app, target, and exact text if relevant."},
            "window_title": {"type": "STRING", "description": "App name or window title to focus before acting; if omitted, ARGUS infers common app names from the objective. If the app is closed, ARGUS opens it and waits for its window."},
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
    objective = str(args.get("objective", "") or "")
    window_title = str(args.get("window_title", "") or "")
    result = await asyncio.to_thread(
        agent.run,
        objective,
        window_title=window_title,
        confirm_sensitive_share=getattr(ctx.client, "confirm_sensitive_file", None),
    )
    if result.status == "blocked":
        wait_for_user = getattr(ctx.client, "wait_for_manual_browser_resolution", None)
        if callable(wait_for_user):
            resumed = await asyncio.to_thread(wait_for_user)
            if resumed:
                # A single new observation resumes the original task only after
                # the user says the challenge is resolved. If it remains, stop.
                result = await asyncio.to_thread(
                    agent.run,
                    objective,
                    window_title=window_title,
                    confirm_sensitive_share=getattr(ctx.client, "confirm_sensitive_file", None),
                )
            else:
                result = type(result)(
                    "aborted",
                    "Não retomei a automação. Repita o pedido depois de resolver a verificação.",
                    result.steps_taken,
                    result.run_id,
                )
    return {"result": result.summary, "status": result.status, "steps_taken": result.steps_taken}

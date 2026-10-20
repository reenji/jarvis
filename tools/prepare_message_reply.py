from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "prepare_message_reply", "description": "Sends a concise reply the user asked ARGUS to write. Use directly; no second approval is needed. Clarify only a genuinely ambiguous recipient or meaning. Legacy approve/cancel actions operate on an existing pending draft.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "enum": ["prepare", "approve", "cancel"], "description": "prepare sends the requested reply immediately; approve/cancel handles a legacy pending draft."}, "platform": {"type": "STRING", "description": "Instagram, iMessage, WhatsApp, Telegram, or another supported platform."}, "receiver": {"type": "STRING", "description": "Recipient name. Optional for the currently open chat."}, "message_text": {"type": "STRING", "description": "Reply text to send."}}, "required": ["action"]}}

async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "prepare_message_reply", args)

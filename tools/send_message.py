from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "send_message", "description": "Sends a user-authorized message through iMessage, WhatsApp, Telegram, Instagram, Discord, Messenger, Signal, or the current chat. Send directly after the user asks; do not ask for approval. Resolve the requested recipient and focus the correct message composer before typing. For Instagram, verify the visible recipient and draft, then send during this call.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "enum": ["send", "approve", "cancel"], "description": "Default: send. Sends immediately when requested; approve/cancel handles a legacy pending draft."}, "receiver": {"type": "STRING", "description": "Recipient contact name. Leave empty for the currently open chat."}, "message_text": {"type": "STRING", "description": "Message content to send."}, "platform": {"type": "STRING", "description": "iMessage, WhatsApp, Telegram, Instagram, Discord, Messenger, Signal, or current/focused."}}, "required": ["platform"]}}

async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "send_message", args)

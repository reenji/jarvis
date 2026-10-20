"""Turn-bound, one-use approval checks for high-impact live tools."""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import uuid
from typing import Any


_CONFIRMATIONS = {
    "yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "confirmed",
    "approve", "approved", "go ahead", "proceed", "do it", "send it",
    "send the email", "send the message", "you can", "yes do that",
    "yes please", "yes please send it", "yes send it", "yes go ahead",
    "sim", "sim pode", "sim pode enviar", "sim pode mandar",
    "sim pode fazer", "sim pode prosseguir", "sim aprovo", "sim confirmo",
    "pode", "pode fazer", "pode fazer isso", "pode prosseguir",
    "pode enviar", "pode enviar sim", "pode enviar agora", "pode enviar o email",
    "pode enviar a mensagem", "pode mandar", "pode mandar agora",
    "pode mandar o email", "pode mandar a mensagem", "confirmo",
    "confirmado", "esta confirmado", "esta aprovado", "aprovo", "aprovado",
    "autorizo", "sim autorizo", "autorizo o envio",
    "manda", "mande", "envia", "envie", "faca", "faca isso", "prossiga",
    "adelante", "confirmo ahora",
}
_CANCELLATIONS = {
    "no", "no thanks", "cancel", "cancel it", "never mind", "stop",
    "nao", "nao obrigado", "cancele", "cancelar", "deixa", "pare",
}


def _normalize_words(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def is_explicit_confirmation(text: str) -> bool:
    return _normalize_words(text) in _CONFIRMATIONS


def is_explicit_cancellation(text: str) -> bool:
    return _normalize_words(text) in _CANCELLATIONS


def draft_fingerprint(draft: dict[str, Any]) -> str:
    """Hash the exact pending draft without retaining its contents here."""
    stable = json.dumps(draft, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def explicit_message_request_matches(text: str, args: dict[str, Any]) -> bool:
    """Require a verbatim recipient, platform, and body in the current request."""
    transcript = _normalize_words(text)
    body = _normalize_words(args.get("message_text"))
    receiver = _normalize_words(args.get("receiver"))
    platform = _normalize_words(args.get("platform"))
    if len(body.replace(" ", "")) < 4 or body not in transcript:
        return False

    body_start = transcript.find(body)
    instruction = transcript[:body_start].strip()
    if not instruction:
        return False

    if re.search(
        r"\b(dont|do not|never|not|no|nao|sem)\b.{0,40}\b(send|text|message|dm|tell|manda|mande|enviar|envia|envie|mensagem|diga|escreva)\b",
        instruction,
    ):
        return False

    intent = re.search(
        r"\b(send|text|message|dm|tell|manda|mande|enviar|envia|envie|mensagem|diga|escreva)\b",
        instruction,
    )
    if not intent:
        return False

    if receiver:
        if receiver not in instruction:
            return False
    elif not re.search(r"\b(this chat|current chat|here|chat atual|neste chat|aqui)\b", instruction):
        return False

    platform_terms = {
        "whatsapp": ("whatsapp", "wpp"),
        "wp": ("whatsapp", "wpp"),
        "imessage": ("imessage", "i message", "apple messages", "sms", "text message"),
        "i message": ("imessage", "i message", "apple messages", "sms", "text message"),
        "messages": ("imessage", "i message", "apple messages", "sms", "text message"),
        "telegram": ("telegram", "tg"),
        "tg": ("telegram", "tg"),
        "instagram": ("instagram", "insta", "ig"),
        "ig": ("instagram", "insta", "ig"),
        "signal": ("signal",),
        "discord": ("discord",),
        "messenger": ("messenger", "facebook messenger"),
        "current": ("this chat", "current chat", "chat atual", "neste chat"),
        "active": ("this chat", "current chat", "chat atual", "neste chat"),
    }
    terms = platform_terms.get(platform, (platform,) if platform else ())
    return bool(terms) and any(term in instruction for term in terms)


class ToolApprovalManager:
    """Require a later, explicit user turn for a specific pending operation."""

    TTL_SECONDS = 300.0

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self.turn_id = 0
        self.transcript = ""
        self.turn_complete = False
        self._pending: dict[str, Any] | None = None
        self._confirmed_pending_id: str | None = None

    @property
    def pending(self) -> dict[str, Any] | None:
        return dict(self._pending) if self._pending else None

    def begin_user_turn(self, text: str = "") -> int:
        self.turn_id += 1
        self.transcript = str(text or "").strip()
        self.turn_complete = False
        self._confirmed_pending_id = None
        return self.turn_id

    def update_user_transcript(self, text: str) -> None:
        self.transcript = str(text or "").strip()

    def finish_user_turn(self, text: str | None = None) -> None:
        if text is not None:
            self.transcript = str(text or "").strip()
        self.turn_complete = True
        if not self._pending:
            return
        if self._is_expired(self._pending):
            self._pending = None
            return
        if self.turn_id <= int(self._pending["created_turn"]):
            return
        if is_explicit_confirmation(self.transcript):
            self._confirmed_pending_id = str(self._pending["id"])
        elif is_explicit_cancellation(self.transcript):
            self._clear_pending()
        else:
            # Approval applies to one immediately following user turn only.
            self._pending = None
            self._confirmed_pending_id = None

    def request_operation(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        key = self._operation_key(tool_name, args)
        pending = self._live_pending()
        if pending is None:
            self._pending = {
                "id": uuid.uuid4().hex,
                "kind": "operation",
                "tool": str(tool_name),
                "key": key,
                "created_turn": self.turn_id,
                "created_at": self._clock(),
            }
            return False, self._approval_required_message(tool_name, args)

        if pending.get("kind") != "operation" or pending.get("key") != key:
            if self._confirmed_pending_id == pending.get("id"):
                self._pending = None
                self._confirmed_pending_id = None
            return False, "The confirmed call does not match the pending operation. Nothing was executed; review and confirm the new operation in a separate turn."

        if not self._is_confirmed_now(pending):
            return False, self._approval_required_message(tool_name, args)

        self._clear_pending()
        return True, ""

    def register_draft(self, kind: str, fingerprint: str) -> bool:
        pending = self._live_pending()
        if pending is not None:
            return False
        self._pending = {
            "id": uuid.uuid4().hex,
            "kind": f"draft:{kind}",
            "fingerprint": str(fingerprint),
            "created_turn": self.turn_id,
            "created_at": self._clock(),
        }
        self._confirmed_pending_id = None
        return True

    def approve_draft(self, kind: str, fingerprint: str) -> tuple[bool, str]:
        pending = self._live_pending()
        if pending is None or pending.get("kind") != f"draft:{kind}":
            return False, "There is no code-verified pending draft approval for this action. Nothing was sent."
        if pending.get("fingerprint") != str(fingerprint):
            self._clear_pending()
            return False, "The pending draft changed after it was presented. Nothing was sent; prepare and review it again."
        if not self._is_confirmed_now(pending):
            return False, "This draft needs an explicit confirmation in a later user turn. Nothing was sent."
        self._clear_pending()
        return True, ""

    def cancel_pending(self) -> None:
        self._clear_pending()

    def cancel_pending_operation(self, tool_name: str) -> bool:
        """Clear one tool's stale operation approval when its policy changes."""
        pending = self._live_pending()
        if not pending or pending.get("kind") != "operation":
            return False
        if pending.get("tool") != str(tool_name):
            return False
        self._clear_pending()
        return True

    @staticmethod
    def _operation_key(tool_name: str, args: dict[str, Any]) -> str:
        value = json.dumps(
            {"tool": str(tool_name), "args": args},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _live_pending(self) -> dict[str, Any] | None:
        if self._pending and self._is_expired(self._pending):
            self._clear_pending()
        return self._pending

    def _is_expired(self, pending: dict[str, Any]) -> bool:
        return self._clock() - float(pending.get("created_at", 0.0)) > self.TTL_SECONDS

    def _is_confirmed_now(self, pending: dict[str, Any]) -> bool:
        return (
            self.turn_complete
            and self.turn_id > int(pending["created_turn"])
            and self._confirmed_pending_id == pending.get("id")
            and is_explicit_confirmation(self.transcript)
        )

    def _clear_pending(self) -> None:
        self._pending = None
        self._confirmed_pending_id = None

    @staticmethod
    def _approval_required_message(tool_name: str, args: dict[str, Any]) -> str:
        exact_call = json.dumps(
            {"tool": tool_name, "arguments": args},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return (
            "APPROVAL_REQUIRED|No action was performed. The exact queued call is "
            f"{exact_call}. Explain its effect and important parameters to the user, then ask for confirmation. "
            "Only after a separate explicit confirmation turn, repeat this same tool call with unchanged arguments."
        )

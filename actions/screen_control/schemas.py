"""Validated data structures shared by the visual screen-control flow."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"
    DONE = "done"
    FAIL = "fail"
    ASK_USER = "ask_user"


@dataclass(frozen=True)
class ScreenAction:
    action: ActionType
    observation: str = ""
    evidence: str = ""
    x: int | None = None
    y: int | None = None
    x2: int | None = None
    y2: int | None = None
    text: str = ""
    keys: tuple[str, ...] = ()
    scroll_amount: int = 0
    seconds: float = 0.6
    target_description: str = ""
    summary: str = ""

    @classmethod
    def from_json(cls, raw: str | dict[str, Any]) -> "ScreenAction":
        if isinstance(raw, str):
            text = raw.strip()
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Resposta de tela não é JSON válido: {exc.msg}") from exc
        else:
            data = raw
        if not isinstance(data, dict):
            raise ValueError("A resposta de tela precisa ser um objeto JSON.")
        try:
            action = ActionType(str(data.get("action", "")).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Ação de tela desconhecida: {data.get('action')!r}") from exc

        def coordinate(name: str) -> int | None:
            value = data.get(name)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} precisa ser uma coordenada entre 0 e 1000.")
            number = int(value)
            if not 0 <= number <= 1000:
                raise ValueError(f"{name} precisa estar entre 0 e 1000.")
            return number

        keys = data.get("keys", []) or []
        if isinstance(keys, str):
            keys = [part.strip() for part in keys.split("+") if part.strip()]
        if not isinstance(keys, (list, tuple)) or any(not isinstance(key, str) for key in keys):
            raise ValueError("keys precisa ser uma lista de teclas.")
        amount = data.get("scroll_amount", 0) or 0
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("scroll_amount precisa ser inteiro.")

        return cls(
            action=action,
            observation=str(data.get("observation", "") or "")[:500],
            evidence=str(data.get("evidence", "") or "")[:300],
            x=coordinate("x"), y=coordinate("y"),
            x2=coordinate("x2"), y2=coordinate("y2"),
            text=str(data.get("text", "") or ""),
            keys=tuple(keys),
            scroll_amount=int(amount),
            seconds=float(data.get("seconds", 0.6) or 0.6),
            target_description=str(data.get("target_description", "") or "")[:300],
            summary=str(data.get("summary", "") or "")[:500],
        )

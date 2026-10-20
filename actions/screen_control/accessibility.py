"""Small Windows UI Automation bridge, used before screenshot coordinates."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from actions.screen_control.window import WindowInfo


@dataclass(frozen=True)
class ControlInfo:
    index: int
    name: str
    control_type: str
    automation_id: str
    left: int
    top: int
    width: int
    height: int
    enabled: bool
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.index, "name": self.name, "type": self.control_type,
            "automation_id": self.automation_id,
            "rect": [self.left, self.top, self.width, self.height],
            "enabled": self.enabled, "selected": self.selected,
        }


def _wrapper_for(window: WindowInfo):
    try:
        from pywinauto import Application
        app = Application(backend="uia").connect(handle=window.handle, timeout=2)
        return app.window(handle=window.handle)
    except ImportError as exc:
        raise RuntimeError("UI Automation no Windows requer pywinauto.") from exc


def describe_controls(window: WindowInfo, *, limit: int = 120) -> list[ControlInfo]:
    """Return a compact, privacy-conscious list of visible named UI controls."""
    try:
        root = _wrapper_for(window)
        controls = root.descendants()
    except Exception:
        return []
    result: list[ControlInfo] = []
    for item in controls:
        if len(result) >= max(1, limit):
            break
        try:
            info = item.element_info
            control_type = str(getattr(info, "control_type", "") or "").strip()
            name = str(getattr(info, "name", "") or "").strip()
            if not name and control_type not in {"Edit", "Document"}:
                name = str(item.window_text() or "").strip()
            if not name and control_type not in {"Edit", "Document", "ComboBox", "Button", "ListItem"}:
                continue
            rect = item.rectangle()
            left, top = int(rect.left), int(rect.top)
            width, height = int(rect.width()), int(rect.height())
            if width <= 0 or height <= 0:
                continue
            result.append(ControlInfo(
                index=len(result), name=name[:180], control_type=control_type[:40],
                automation_id=str(getattr(info, "automation_id", "") or "")[:100],
                left=left, top=top, width=width, height=height,
                enabled=bool(item.is_enabled()),
                selected=bool(item.is_selected()) if hasattr(item, "is_selected") else False,
            ))
        except Exception:
            continue
    return result


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


_STOP_WORDS = {
    "the", "a", "an", "is", "in", "on", "at", "of", "to", "for", "with",
    "button", "field", "search", "result", "conversation", "chat", "composer",
    "message", "text", "box", "element", "visible", "active", "window", "exactly",
    "labeled", "label", "target", "click", "open", "select", "row", "list", "item",
    "do", "campo", "botao", "mensagem", "conversa", "resultado", "pesquisa",
    "abrir", "selecionar", "visivel", "janela", "ativo", "exatamente", "rotulado",
}


def _target_terms(target: str) -> tuple[str, ...]:
    quoted = re.findall(r"['\"“”‘’]([^'\"“”‘’]+)['\"“”‘’]", str(target or ""))
    source = " ".join(quoted) if quoted else str(target or "")
    return tuple(word for word in _normalize(source).split() if word not in _STOP_WORDS)


def _score(target: str, name: str) -> float:
    wanted = _target_terms(target)
    actual = _normalize(name).split()
    if not wanted or not actual:
        return 0.0
    if " ".join(wanted) == " ".join(actual):
        return 1.0
    if " ".join(wanted) in " ".join(actual):
        return 0.98
    matches = sum(1 for word in wanted if word in actual)
    return matches / len(wanted)


def _find_control(window: WindowInfo, target: str, *, text_only: bool = False):
    if not target.strip():
        return None, "missing_target"
    try:
        root = _wrapper_for(window)
        controls = root.descendants()
    except Exception as exc:
        return None, f"uia_unavailable:{exc}"

    candidates: list[tuple[float, Any, str, str]] = []
    for item in controls:
        try:
            info = item.element_info
            control_type = str(getattr(info, "control_type", "") or "").strip()
            name = str(getattr(info, "name", "") or "").strip()
            if not name and control_type not in {"Edit", "Document"}:
                name = str(item.window_text() or "").strip()
            if text_only and control_type not in {"Edit", "Document", "ComboBox"}:
                continue
            if not item.is_enabled() or not name:
                continue
            score = _score(target, name)
            if score >= 0.55:
                candidates.append((score, item, name, control_type))
        except Exception:
            continue
    if not candidates:
        return None, "not_found"
    candidates.sort(key=lambda row: row[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.12:
        return None, "ambiguous"
    return candidates[0][1], "ok"


def click_control(
    window: WindowInfo, target: str, *, button: str = "left", double: bool = False,
) -> tuple[bool, str]:
    control, status = _find_control(window, target)
    if status != "ok":
        return False, status
    try:
        if button == "right":
            control.right_click_input()
        elif double:
            control.double_click_input()
        else:
            control.click_input()
        label = "right click" if button == "right" else "double click" if double else "click"
        return True, f"UI Automation {label}"
    except Exception as exc:
        return False, f"click_failed:{exc}"


def focus_text_control(window: WindowInfo, target: str) -> tuple[bool, str]:
    control, status = _find_control(window, target, text_only=True)
    if status != "ok":
        return False, status
    try:
        control.set_focus()
        return True, "UI Automation text focus"
    except Exception as exc:
        return False, f"focus_failed:{exc}"

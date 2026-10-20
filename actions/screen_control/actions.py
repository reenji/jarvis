"""Execute validated screen actions, preferring named Windows controls."""

from __future__ import annotations

import time
from dataclasses import dataclass

from actions.screen_control.accessibility import click_control, focus_text_control
from actions.screen_control.capture import Capture
from actions.screen_control.schemas import ActionType, ScreenAction
from actions.screen_control.window import get_active_window


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    detail: str
    duration: float


def to_absolute(x_norm: int, y_norm: int, capture: Capture) -> tuple[int, int]:
    """Map normalized screenshot coordinates to original display pixels."""
    if not (0 <= x_norm <= 1000 and 0 <= y_norm <= 1000):
        raise ValueError("Coordenadas normalizadas precisam estar entre 0 e 1000.")
    x = capture.origin_x + round((x_norm / 1000) * max(0, capture.source_width - 1))
    y = capture.origin_y + round((y_norm / 1000) * max(0, capture.source_height - 1))
    return x, y


def _type_text(
    text: str, target: str, x: int | None, y: int | None, capture: Capture,
    *, allow_browser_search: bool = False,
) -> str:
    import pyautogui

    window = get_active_window()
    focused = False
    focus_detail = ""
    if target:
        focused, focus_detail = focus_text_control(window, target)
    if not focused and x is not None and y is not None:
        abs_x, abs_y = to_absolute(x, y, capture)
        if not _inside_capture(abs_x, abs_y, capture):
            raise RuntimeError("O campo de texto indicado está fora da janela em foco.")
        pyautogui.click(abs_x, abs_y)
        time.sleep(0.12)

    # Only paste after the operating system confirms that a text control has focus.
    from actions.safe_text_entry import validate_safe_text_target
    validation = validate_safe_text_target("generic", allow_browser_search=allow_browser_search)
    if not validation.ok:
        raise RuntimeError(validation.message)

    try:
        import pyperclip
        previous = pyperclip.paste()
        try:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)
        finally:
            pyperclip.copy(previous)
        return "Texto colado em campo de texto verificado."
    except ImportError:
        from actions.safe_text_entry import safe_type_text
        typed = safe_type_text(text, purpose="generic")
        if not typed.ok:
            raise RuntimeError(typed.message)
        return typed.message
    except Exception as exc:
        raise RuntimeError(f"Falha ao colar texto: {exc}") from exc


def _inside_capture(x: int, y: int, capture: Capture) -> bool:
    return (
        capture.origin_x <= x < capture.origin_x + capture.source_width
        and capture.origin_y <= y < capture.origin_y + capture.source_height
    )


def execute(
    action: ScreenAction, capture: Capture, *, mouse_duration: float = 0.2,
    allow_browser_search: bool = False,
) -> ActionResult:
    started = time.monotonic()
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        window = get_active_window()
        if window.handle != capture.window.handle:
            raise RuntimeError("A janela em foco mudou durante a ação; não executei o clique.")

        if action.action in {ActionType.CLICK, ActionType.DOUBLE_CLICK, ActionType.RIGHT_CLICK}:
            used_uia = False
            if action.target_description:
                clicked, detail = click_control(
                    window,
                    action.target_description,
                    button="right" if action.action == ActionType.RIGHT_CLICK else "left",
                    double=action.action == ActionType.DOUBLE_CLICK,
                )
                if clicked:
                    used_uia = True
                elif detail == "ambiguous" and (action.x is None or action.y is None):
                    raise RuntimeError("Encontrei mais de um controle possível para o alvo.")
            if not used_uia:
                if action.x is None or action.y is None:
                    raise RuntimeError("A decisão não informou um alvo acessível nem coordenadas.")
                x, y = to_absolute(action.x, action.y, capture)
                if not _inside_capture(x, y, capture):
                    raise RuntimeError("O clique indicado está fora da janela em foco.")
                pyautogui.moveTo(x, y, duration=mouse_duration)
                clicks = 2 if action.action == ActionType.DOUBLE_CLICK else 1
                button = "right" if action.action == ActionType.RIGHT_CLICK else "left"
                pyautogui.click(x, y, clicks=clicks, button=button)

        elif action.action == ActionType.TYPE_TEXT:
            if not action.text:
                raise RuntimeError("A ação de digitar veio sem texto.")
            detail = _type_text(
                action.text, action.target_description, action.x, action.y, capture,
                allow_browser_search=allow_browser_search,
            )
            return ActionResult(True, detail, time.monotonic() - started)

        elif action.action == ActionType.PRESS_KEY:
            if not action.keys:
                raise RuntimeError("A ação press_key veio sem tecla.")
            pyautogui.press(action.keys[0])

        elif action.action == ActionType.HOTKEY:
            if not action.keys:
                raise RuntimeError("A ação hotkey veio sem teclas.")
            pyautogui.hotkey(*action.keys)

        elif action.action == ActionType.SCROLL:
            if action.x is not None and action.y is not None:
                x, y = to_absolute(action.x, action.y, capture)
            else:
                x = capture.origin_x + capture.source_width // 2
                y = capture.origin_y + capture.source_height // 2
            if not _inside_capture(x, y, capture):
                raise RuntimeError("O ponto de rolagem indicado está fora da janela em foco.")
            pyautogui.moveTo(x, y, duration=mouse_duration)
            pyautogui.scroll(action.scroll_amount)

        elif action.action == ActionType.DRAG:
            if None in (action.x, action.y, action.x2, action.y2):
                raise RuntimeError("A ação drag precisa de origem e destino.")
            x1, y1 = to_absolute(action.x, action.y, capture)
            x2, y2 = to_absolute(action.x2, action.y2, capture)
            if not (_inside_capture(x1, y1, capture) and _inside_capture(x2, y2, capture)):
                raise RuntimeError("O arraste ultrapassaria a janela em foco.")
            pyautogui.moveTo(x1, y1, duration=mouse_duration)
            pyautogui.dragTo(x2, y2, duration=max(0.2, mouse_duration), button="left")

        elif action.action == ActionType.WAIT:
            time.sleep(min(3.0, max(0.1, action.seconds)))

        else:
            raise RuntimeError(f"{action.action.value} não é uma ação executável.")

        return ActionResult(True, "Ação executada.", time.monotonic() - started)
    except Exception as exc:
        return ActionResult(False, str(exc), time.monotonic() - started)

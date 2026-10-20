"""Screen capture with source bounds retained for accurate click mapping."""

from __future__ import annotations

import io
import time
from dataclasses import dataclass

from actions.screen_control.window import WindowInfo, get_active_window


@dataclass(frozen=True)
class Capture:
    image_bytes: bytes
    image_width: int
    image_height: int
    source_width: int
    source_height: int
    origin_x: int
    origin_y: int
    scale: float
    timestamp: float
    window: WindowInfo


def capture_active_window(max_image_side: int = 1568) -> Capture:
    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("A captura de tela requer mss e Pillow.") from exc

    window = get_active_window()
    bounds = {"left": window.left, "top": window.top, "width": window.width, "height": window.height}
    try:
        with mss.mss() as sct:
            raw = sct.grab(bounds)
            image = Image.frombytes("RGB", raw.size, raw.rgb)
    except Exception as exc:
        raise RuntimeError(f"Não consegui capturar a janela {window.title!r}: {exc}") from exc

    source_width, source_height = image.size
    factor = min(1.0, max_image_side / max(source_width, source_height))
    if factor < 1.0:
        size = (max(1, round(source_width * factor)), max(1, round(source_height * factor)))
        image = image.resize(size, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return Capture(
        output.getvalue(), image.width, image.height, source_width, source_height,
        window.left, window.top, factor, time.time(), window,
    )


def capture_screen(max_image_side: int = 1568) -> Capture:
    """Capture the desktop bounds; the active window still scopes action safety."""
    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("A captura de tela requer mss e Pillow.") from exc
    window = get_active_window()
    try:
        with mss.mss() as sct:
            monitor = dict(sct.monitors[0])
            raw = sct.grab(monitor)
            image = Image.frombytes("RGB", raw.size, raw.rgb)
    except Exception as exc:
        raise RuntimeError(f"Não consegui capturar a tela: {exc}") from exc
    source_width, source_height = image.size
    factor = min(1.0, max_image_side / max(source_width, source_height))
    if factor < 1.0:
        image = image.resize((round(source_width * factor), round(source_height * factor)), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return Capture(output.getvalue(), image.width, image.height, source_width, source_height, monitor["left"], monitor["top"], factor, time.time(), window)

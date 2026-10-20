"""Stable desktop client facade exposed by :mod:`ui`."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class ArgusUI:

    def __init__(
        self,
        face_path: str,
        size=None,
        *,
        intro_tts_renderer=None,
        segmented_intro_tts_renderer=None,
    ):
        _configure_intro_tts_renderers(intro_tts_renderer, segmented_intro_tts_renderer)
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")

        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def operational_ready(self) -> bool:
        window = self._win
        return bool(
            window._ready
            and not getattr(window, "_interaction_gated", False)
            and not getattr(window, "_intro_in_progress", False)
            and not getattr(window, "_intro_voice_preparing", False)
            and getattr(window, "_intro_overlay", None) is None
            and getattr(window, "_overlay", None) is None
        )

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def _voice_combo(self):
        """Expose the legacy selector used by the live engine voice fallback."""
        return self._win._voice_combo

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_voice_change(self):
        return self._win.on_voice_change

    @on_voice_change.setter
    def on_voice_change(self, cb):
        self._win.on_voice_change = cb

    @property
    def on_voice_preferences_change(self):
        return self._win.on_voice_preferences_change

    @on_voice_preferences_change.setter
    def on_voice_preferences_change(self, cb):
        self._win.on_voice_preferences_change = cb

    @property
    def on_direct_computer_control_change(self):
        return self._win.on_direct_computer_control_change

    @on_direct_computer_control_change.setter
    def on_direct_computer_control_change(self, cb):
        self._win.on_direct_computer_control_change = cb

    @property
    def on_name_change(self):
        return self._win.on_name_change

    @on_name_change.setter
    def on_name_change(self, cb):
        self._win.on_name_change = cb

    @property
    def on_tts_provider_change(self):
        return self._win.on_tts_provider_change

    @on_tts_provider_change.setter
    def on_tts_provider_change(self, cb):
        self._win.on_tts_provider_change = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)
        self._win._parse_log_for_context(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def sync_voice_display(self, voice_name: str):
        self._win._voice_sig.emit(voice_name)

    def show_subtitle(self, text: str):
        """Thread-safe subtitle display request."""
        try:
            # Don't show subtitles when muted.
            if getattr(self._win, "_muted", False) or (
                getattr(self._win, "hud", None) is not None and getattr(self._win.hud, "muted", False)
            ):
                return
            self._win._sub_sig.emit(text)
        except Exception:
            pass

    def clear_subtitle(self):
        """Thread-safe subtitle clear."""
        try:
            self._win._sub_clear_sig.emit()
        except Exception:
            pass

    def start_subtitle_hold(self):
        """Thread-safe: start the subtitle fade-out hold timer (call when ARGUS finishes talking)."""
        try:
            self._win._sub_hold_sig.emit()
        except Exception:
            pass

    def show_vision_preview(self, source: str = "screen"):
        """Show a thread-safe draggable live screen or camera preview."""
        self._win._vision_preview_sig.emit(source)

    def hide_vision_preview(self, delay_ms: int = 1800):
        """Mark vision complete and close its preview after a short hold."""
        self._win._vision_preview_hide_sig.emit(max(0, int(delay_ms)))

    def show_research_progress(self, question: str):
        """Open the compact background Deep Research status surface."""
        self._win._research_progress_sig.emit({
            "question": str(question or "Deep research"),
            "percent": 0,
            "phase": "Queued",
            "artifacts": [],
            "warnings": [],
        })

    def update_research_progress(
        self,
        question: str,
        percent: int,
        phase: str,
        artifacts: list[str] | None = None,
        warnings: list[str] | None = None,
    ):
        """Thread-safe update for real research phases and artifacts."""
        self._win._research_progress_sig.emit({
            "question": str(question or "Deep research"),
            "percent": max(0, min(100, int(percent or 0))),
            "phase": str(phase or "Researching"),
            "artifacts": list(artifacts or []),
            "warnings": list(warnings or []),
        })

    def finish_research_progress(self, state: str, detail: str):
        """Show a visible research failure or cancellation without crashing the UI."""
        self._win._research_progress_finish_sig.emit(str(state), str(detail))

    def hide_research_progress(self):
        self._win._research_progress_hide_sig.emit()

    def show_presentation_progress(self, title: str, visible: bool = False):
        """Show the chosen foreground or background presentation status surface."""
        self._win._presentation_progress_sig.emit({
            "question": str(title or "Presentation"),
            "percent": 0,
            "phase": "Queued",
            "artifacts": [],
            "warnings": [],
            "visible": bool(visible),
        })

    def update_presentation_progress(
        self,
        title: str,
        percent: int,
        phase: str,
        visible: bool = False,
        artifacts: list[str] | None = None,
        warnings: list[str] | None = None,
    ):
        """Thread-safe update using real presentation build phases."""
        self._win._presentation_progress_sig.emit({
            "question": str(title or "Presentation"),
            "percent": max(0, min(100, int(percent or 0))),
            "phase": str(phase or "Building presentation"),
            "artifacts": list(artifacts or []),
            "warnings": list(warnings or []),
            "visible": bool(visible),
        })

    def finish_presentation_progress(self, state: str, detail: str):
        """Display cancellation or failure without leaving stale task state."""
        self._win._presentation_progress_finish_sig.emit(str(state), str(detail))

    def hide_presentation_progress(self):
        self._win._presentation_progress_hide_sig.emit()

    # ── New UI enhancement methods ───────────────────────────────────────

    def show_toast(self, message: str, toast_type: str = "info"):
        """Thread-safe toast notification. Types: info, success, warning, error."""
        try:
            self._win._show_toast(message, toast_type)
        except Exception:
            pass

    def show_tool_progress(self, tool_name: str):
        """Show tool execution progress indicator."""
        try:
            self._win._tool_progress.show_tool(tool_name)
        except Exception:
            pass

    def hide_tool_progress(self):
        """Hide tool execution progress indicator."""
        try:
            self._win._tool_progress.hide_tool()
        except Exception:
            pass

    def set_theme(self, theme_key: str):
        """Thread-safe theme change requested by ARGUS."""
        self._win._theme_sig.emit(theme_key)

    def set_graphics_quality(self, quality: str):
        """Thread-safe graphics quality change requested by ARGUS."""
        self._win._graphics_sig.emit(quality)

    def handle_ui_command(self, action: str):
        """Thread-safe access to secondary interface utilities."""
        self._win._ui_command_sig.emit(action)

    def toggle_compact_mode(self):
        """Toggle compact/mini mode."""
        self._win._toggle_compact_mode()

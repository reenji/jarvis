"""Mainwindowsettings main-window behavior."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

class _MainWindowSettingsMixin:
    def _toggle_shortcuts_overlay(self):
        if self._shortcuts_overlay and self._shortcuts_overlay.isVisible():
            self._shortcuts_overlay.hide()
            return
        cw = self.centralWidget()
        ov = ShortcutsOverlay(cw)
        ow, oh = 420, 380
        ov.setGeometry(
            (cw.width() - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.show()
        self._shortcuts_overlay = ov

    def _show_settings(self):
        if self._settings_overlay and self._settings_overlay.isVisible():
            self._settings_overlay.hide()
            return
        # Get current name
        current_name = ""
        try:
            from memory.memory_manager import load_memory
            memory = load_memory()
            name_entry = memory.get("identity", {}).get("name")
            if isinstance(name_entry, dict):
                current_name = name_entry.get("value", "")
            elif isinstance(name_entry, str):
                current_name = name_entry
        except Exception:
            pass

        voice_preferences = load_voice_preferences(UI_SETTINGS_FILE)
        direct_control_enabled = load_direct_computer_control(UI_SETTINGS_FILE)

        cw = self.centralWidget()
        ov = SettingsOverlay(
            cw,
            current_name=current_name,
            current_voice=self._get_selected_voice(),
            current_response_style=voice_preferences["response_style"],
            current_vad_silence_ms=voice_preferences["vad_silence_ms"],
            current_theme=ThemeManager.current_name(),
            current_graphics=self._graphics_quality,
            current_graphics_mode=get_graphics_mode(),
            replay_intro=_load_intro_settings()[1],
            current_motion_preference=self._motion_preference,
            direct_computer_control_enabled=direct_control_enabled,
        )
        ow, oh = 600, 500
        ov.setGeometry(
            (cw.width() - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.name_changed.connect(self._on_settings_name)
        ov.theme_changed.connect(self._on_settings_theme)
        ov.graphics_changed.connect(self._on_settings_graphics)
        ov.graphics_mode_changed.connect(self._on_settings_graphics_mode)
        ov.motion_preference_changed.connect(self._on_motion_preference_changed)
        ov.intro_replay_changed.connect(self._on_intro_replay_changed)
        ov.tour_replay_requested.connect(self._request_manual_tour_replay)
        ov.voice_selector_requested.connect(self._show_voice_select)
        ov.voice_preferences_changed.connect(self._on_voice_preferences_changed)
        ov.direct_computer_control_changed.connect(self._on_direct_computer_control_changed)
        ov.show()
        self._settings_overlay = ov

    def _on_voice_preferences_changed(self, response_style: str, vad_silence_ms: int):
        before = load_voice_preferences(UI_SETTINGS_FILE)
        after = save_voice_preferences(
            path=UI_SETTINGS_FILE,
            response_style=response_style,
            vad_silence_ms=vad_silence_ms,
        )
        if after == before:
            return
        if self.on_voice_preferences_change:
            try:
                self.on_voice_preferences_change()
            except Exception as exc:
                self._log.append_log(f"SYS: Voice preferences callback error: {exc}")
        if before["response_style"] != after["response_style"]:
            self._log.append_log(f"SYS: Voice response style set to {after['response_style']}.")
        if before["vad_silence_ms"] != after["vad_silence_ms"]:
            self._log.append_log(f"SYS: Speech end pause set to {after['vad_silence_ms']} ms.")

    def _on_direct_computer_control_changed(self, enabled: bool):
        before = load_direct_computer_control(UI_SETTINGS_FILE)
        after = save_direct_computer_control(enabled, UI_SETTINGS_FILE)
        if after == before:
            return
        if self.on_direct_computer_control_change:
            try:
                self.on_direct_computer_control_change()
            except Exception as exc:
                self._log.append_log(f"SYS: Direct-control callback error: {exc}")
        state = "enabled" if after else "disabled"
        self._log.append_log(f"SYS: Direct mouse and keyboard control {state}.")

    def _on_settings_name(self, name: str):
        if name:
            self._on_name_done(name)

    def _on_settings_theme(self, key: str):
        ThemeManager.set_theme(key)

    def _on_settings_graphics(self, quality: str):
        self._apply_graphics_quality_live(quality)

    def _on_settings_graphics_mode(self, mode: str):
        settings = _read_ui_settings()
        settings["graphics_quality_mode"] = "auto" if mode == "auto" else "manual"
        UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        if mode == "auto":
            self._start_auto_graphics_detection()

    def _on_motion_preference_changed(self, preference: str):
        value = str(preference or "system")
        if value not in {"system", "reduced", "full"}:
            value = "system"
        settings = _read_ui_settings()
        settings["motion_preference"] = value
        UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        self._motion_preference = value
        from ui.motion import resolve_reduced_motion

        self._reduced_motion = resolve_reduced_motion(value)
        if hasattr(self, "_orb"):
            self._orb.set_reduced_motion(self._reduced_motion)
        if hasattr(self, "_activity_visualizer"):
            self._activity_visualizer.set_reduced_motion(self._reduced_motion)
        if self._compact_widget is not None:
            self._compact_widget.set_reduced_motion(self._reduced_motion)

    def _on_intro_replay_changed(self, enabled: bool):
        settings = _read_ui_settings()
        settings.pop("intro_every_launch", None)
        settings["startup_greeting_enabled"] = bool(enabled)
        settings["intro_version"] = INTRO_SEQUENCE_VERSION
        UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        self._pending_greeting_enabled = bool(enabled)

    def _show_vision_preview(self, source: str):
        if self._vision_preview is None:
            self._vision_preview = VisionPreviewWindow(self.centralWidget())
        self._vision_preview.set_graphics_quality(self._graphics_quality)
        self._vision_preview.start(source)

    def _hide_vision_preview(self, delay_ms: int = 1800):
        if self._vision_preview is not None:
            self._vision_preview.finish(delay_ms)

    def _apply_graphics_quality_live(self, quality: str):
        """Persist and apply a graphics profile to every active renderer."""
        value = set_graphics_quality(quality)
        self._graphics_quality = value
        profile = GRAPHICS_PROFILES[value]

        if hasattr(self, "hud"):
            self.hud.set_graphics_quality(value)
            self.hud._tmr.stop()
        if hasattr(self, "_orb"):
            self._orb.set_graphics_quality(value)
        if hasattr(self, "_activity_visualizer"):
            self._activity_visualizer.set_graphics_quality(value)
        if self._compact_widget is not None:
            self._compact_widget.set_graphics_quality(value)
        if hasattr(self, "_ai_canvas"):
            self._ai_canvas.set_graphics_quality(value)
            if hasattr(self._ai_canvas, "_tmr"):
                self._ai_canvas._tmr.stop()
        if hasattr(self, "_metric_tmr"):
            self._metric_tmr.setInterval(int(profile["metrics_ms"]))
        if self._vision_preview is not None:
            self._vision_preview.set_graphics_quality(value)
        if self._settings_overlay:
            self._settings_overlay._current_graphics = value
            self._settings_overlay._highlight_graphics(value)

        quality_label = {"low": "baixa", "medium": "média", "high": "alta"}[value]
        if hasattr(self, "_log"):
            self._log.append_log(f"SYS: Qualidade gráfica definida: {quality_label}.")
        if hasattr(self, "_popup_manager"):
            self._show_toast(f"Qualidade gráfica: {quality_label}", "success")

    def _cycle_theme(self):
        try:
            names = ThemeManager.theme_names()
            cur = ThemeManager.current_name()
            idx = names.index(cur) if cur in names else 0
            next_key = names[(idx + 1) % len(names)]
            ThemeManager.set_theme(next_key)
            display = ThemeManager.theme_display_name(next_key)
            ToastManager.show_toast(self.centralWidget(),
                                    f"Theme: {display}", "info", 2000)
        except Exception:
            pass

    def _on_theme_changed(self, key: str):
        """Apply a selected theme immediately across the visible interface."""
        from PyQt6.QtGui import QPalette

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(C.BG))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(C.WHITE))
        palette.setColor(QPalette.ColorRole.Base, QColor(C.DARK))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(C.DARK2))
        palette.setColor(QPalette.ColorRole.Text, QColor(C.WHITE))
        palette.setColor(QPalette.ColorRole.Button, QColor(C.PANEL2))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(C.WHITE))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(C.PRI))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(C.BG))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {C.BG}; }}
            QTextEdit, QPlainTextEdit, QTextBrowser {{
                background: {C.DARK}; color: {C.WHITE}; border: none;
            }}
        """)
        if self.centralWidget():
            self.centralWidget().setStyleSheet(f"QWidget#argusRoot {{ background: {C.BG}; }}")
        if hasattr(self, "_middle_section"):
            self._middle_section.setStyleSheet(f"background: {C.BG};")
        if hasattr(self, "_ai_core_wrap"):
            self._ai_core_wrap.setStyleSheet(f"QWidget#aiCore {{ background: {C.BG}; }}")
        if hasattr(self, "_left_panel"):
            self._left_panel.setStyleSheet(f"""
                QWidget#leftRail {{
                    background: {C.PANEL}; border-right: 1px solid {C.STEEL};
                }}
            """)
        if hasattr(self, "_right_panel"):
            self._right_panel.setStyleSheet(f"""
                QWidget#rightRail {{
                    background: {C.PANEL}; border-left: 1px solid {C.BORDER};
                }}
            """)
        if hasattr(self, "_command_bar"):
            self._style_command_rail()

        self._style_header()
        self._style_splitter()
        self._style_left_nav()
        self._style_command_controls()
        self._style_maker_signature()
        self._update_theme_btn()
        if hasattr(self, "_mission"):
            self._mission.refresh_theme()
        if hasattr(self, "_focus_dialogue"):
            self._focus_dialogue.refresh_theme()
        if hasattr(self, "_chat_bubble"):
            self._chat_bubble.refresh_theme()
        if hasattr(self, "_connection_status"):
            self._connection_status.refresh_theme()
        if hasattr(self, "_research_progress"):
            self._research_progress.refresh_theme()
        if hasattr(self, "_subtitle"):
            self._subtitle._done_col = qcol(C.TEXT)
            self._subtitle._active_col = qcol(C.PRI)
        if self._settings_overlay:
            self._settings_overlay.refresh_theme()
        if self._vision_preview is not None:
            self._vision_preview.refresh_theme()

        for spark, color in (
            (getattr(self, "_spark_cpu", None), C.PRI),
            (getattr(self, "_spark_mem", None), C.ENERGY),
            (getattr(self, "_spark_net", None), C.ACC2),
            (getattr(self, "_spark_tmp", None), C.ACC),
        ):
            if spark is not None:
                spark._color = color

        for widget in self.findChildren(QWidget):
            widget.update()

        if hasattr(self, "_style_navigation_rail"):
            self._style_navigation_rail()
        if hasattr(self, "hud") and hasattr(self, "_apply_state"):
            self._apply_state(self.hud.state)
        if self._compact_widget is not None:
            self._compact_widget.refresh_theme()

        try:
            settings_dir = Path.home() / ".argus" / "config"
            settings_dir.mkdir(parents=True, exist_ok=True)
            settings_file = settings_dir / "settings.json"
            try:
                settings = json.loads(settings_file.read_text(encoding="utf-8")) if settings_file.exists() else {}
            except Exception:
                settings = {}
            settings["theme"] = key
            settings_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        except Exception:
            pass

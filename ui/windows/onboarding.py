"""Mainwindowonboarding main-window behavior."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

class _MainWindowOnboardingMixin:
    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            if "gemini_api_key" in d:
                d.pop("gemini_api_key", None)
                try:
                    API_FILE.write_text(json.dumps(d, indent=4), encoding="utf-8")
                except Exception:
                    pass
            return bool(d.get("os_system"))
        except Exception:
            return False

    def _load_saved_voice(self):
        try:
            if hasattr(self, '_voice_combo'):
                d = json.loads(API_FILE.read_text(encoding="utf-8")) if API_FILE.exists() else {}
                voice_name = d.get("voice_name", d.get("tts_voice_id", "charon"))
                if isinstance(voice_name, str):
                    voice_name = voice_name.strip().lower()
                if voice_name not in VOICE_VALUE_TO_LABEL:
                    voice_name = "charon"
                index = self._voice_combo.findData(voice_name)
                if index >= 0:
                    self._voice_combo.setCurrentIndex(index)
                else:
                    self._voice_combo.setCurrentIndex(self._voice_combo.findData("charon"))
                os.environ["GEMINI_VOICE_NAME"] = self._get_selected_voice()
        except Exception:
            pass

    def _sync_voice_combo(self, voice_name: str):
        self._voice_combo.blockSignals(True)
        idx = self._voice_combo.findData(voice_name.lower())
        if idx >= 0:
            self._voice_combo.setCurrentIndex(idx)
        self._voice_combo.blockSignals(False)

    def _show_setup(self):
        cw = self.centralWidget()
        self._ensure_startup_backdrop()
        ov = SetupOverlay(cw, replay_every_launch=self._pending_greeting_enabled)
        ov.setFixedSize(460, 540)
        ov.done.connect(self._on_setup_done)
        self._overlay = ov
        ov.show()
        ov.raise_()
        ov._center_in_parent()

    def _runtime_on_setup_done(self, key: str, os_name: str, remember_key: bool):
        from core.api_key_validator import normalize_gemini_api_key

        normalized_key = normalize_gemini_api_key(key)
        verified_key = getattr(self._overlay, "_verified_key", "") if self._overlay else ""
        if not normalized_key or normalized_key != verified_key:
            self._log.append_log("ERR: Setup blocked because the Gemini API key was not verified.")
            self._ready = False
            return
        key = normalized_key

        # Persist API key only if user explicitly opts in.
        if remember_key and isinstance(key, str) and key.strip():
            try:
                store = get_secret_store()
                store.set("gemini_api_key", key.strip())
                self._log.append_log("SYS: Gemini API key saved to OS keychain.")
            except Exception as e:
                self._log.append_log(f"SYS: Could not save key to keychain: {e}")

        os.makedirs(CONFIG_DIR, exist_ok=True)

        try:
            cfg = json.loads(API_FILE.read_text(encoding="utf-8")) if API_FILE.exists() else {}
        except Exception:
            cfg = {}
        # Do NOT persist the Gemini API key to disk. Keep it in-memory for this session only.
        cfg.pop("gemini_api_key", None)
        cfg["os_system"] = os_name
        API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        try:
            # Set the API key for this running process only. This ensures the key is
            # available to modules that read `os.environ['GEMINI_API_KEY']` without
            # writing it to disk — the user must re-enter it on next start.
            if isinstance(key, str) and key.strip():
                os.environ["GEMINI_API_KEY"] = key.strip()
                self._log.append_log("SYS: Gemini API key set for this session (not saved).")
        except Exception:
            pass
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log("SYS: INITIATING SYSTEMS, SIR...")
        self._log.append_log("SYS: CORE SYSTEMS ONLINE")
        self._log.append_log("SYS: NEURAL NETWORK ACTIVE  [OK]")
        self._log.append_log("SYS: PARALLAX UI COMPLETE   [OK]")
        self._log.append_log("SYS: VOICE SYNTHESIS READY  [OK]")
        self._log.append_log(f"SYS: PLATFORM {os_name.upper()} DETECTED")
        self._log.append_log("SYS: ARGUS MARK XXXIX - ALL SYSTEMS NOMINAL")
        # After setup: show voice popup first, then name popup
        self._show_voice_select_then_name()

    def _ensure_startup_backdrop(self):
        cw = self.centralWidget()
        if cw is None:
            return
        backdrop = getattr(self, "_startup_backdrop", None)
        if backdrop is None:
            backdrop = QWidget(cw)
            backdrop.setObjectName("StartupBackdrop")
            backdrop.setAccessibleName("ARGUS startup setup")
            backdrop.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            backdrop.setStyleSheet(f"background: {C.BG};")
            self._startup_backdrop = backdrop
        backdrop.setGeometry(cw.rect())
        backdrop.show()
        backdrop.lower()
        if getattr(self, "_overlay", None) is not None:
            self._overlay.raise_()

    def _clear_startup_backdrop(self):
        backdrop = getattr(self, "_startup_backdrop", None)
        if backdrop is not None:
            backdrop.hide()
            backdrop.deleteLater()
            self._startup_backdrop = None

    def _on_setup_done(self, key: str, os_name: str, remember_key: bool):
        from core.api_key_validator import normalize_gemini_api_key, validate_gemini_api_key

        normalized = normalize_gemini_api_key(key)
        overlay = self._overlay
        if overlay is not None:
            self._pending_greeting_enabled = overlay.replay_intro_enabled()
        completed, _saved_greeting = _load_intro_settings()
        self._skip_first_tour = bool(
            not completed and overlay is not None and overlay.skip_first_tour_enabled()
        )
        self._intro_should_play = (
            (not completed and not self._skip_first_tour)
            or self._pending_greeting_enabled
        )
        self._startup_sequence_kind = (
            "tour" if not completed and not self._skip_first_tour
            else "greeting" if self._pending_greeting_enabled
            else ""
        )
        verified = getattr(overlay, "_verified_key", "") if overlay is not None else ""
        if not normalized or normalized != verified:
            if overlay is not None:
                overlay._key_input.setText(normalized)
                overlay.set_validating()

            def _validate():
                result = validate_gemini_api_key(normalized)
                if overlay is not None:
                    overlay.validation_finished.emit(
                        result.valid, result.message, normalized, remember_key
                    )

            threading.Thread(target=_validate, daemon=True).start()
            return

        self._finish_setup_after_key_validation(
            normalized, os_name, remember_key,
            ApiKeyValidationResult(True, "API key validated."),
        )

    def _finish_setup_after_key_validation(self, key, os_name, remember_key, result):
        if not result.valid:
            if self._overlay is not None:
                self._overlay.set_validation_error(result.message)
            self._ready = False
            return
        if remember_key:
            try:
                get_secret_store().set("gemini_api_key", key)
            except (OSError, RuntimeError, ValueError) as exc:
                self._log.append_log(f"ERR: Could not save key to keychain: {exc}")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            cfg = json.loads(API_FILE.read_text(encoding="utf-8")) if API_FILE.exists() else {}
        except (OSError, json.JSONDecodeError):
            cfg = {}
        cfg.pop("gemini_api_key", None)
        cfg["os_system"] = os_name
        API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        os.environ["GEMINI_API_KEY"] = key
        if getattr(self, "_skip_first_tour", False):
            # A deliberate first-run skip should not trigger the tour next launch.
            _save_intro_settings(True, self._pending_greeting_enabled)
        self._ready = False
        self._pending_ready_after_intro = True
        self._interaction_gated = True
        if self._intro_should_play:
            self._prepare_intro_voice()
        else:
            if self._overlay is not None:
                self._overlay.hide()
                self._overlay = None
            self._clear_startup_backdrop()
            self._continue_after_intro()

    def _prepare_intro_voice(self):
        kind = self._startup_sequence_kind or "greeting"
        if kind == "tour":
            self._startup_chapters = _tour_chapters(datetime.now())
            self._startup_captions = tuple(item.caption for item in self._startup_chapters)
            self._startup_narration = " ".join(self._startup_captions)
        else:
            self._startup_chapters = ()
            self._startup_captions = FirstRunIntroOverlay._CAPTIONS
            self._startup_narration = " ".join(self._startup_captions)
        self._intro_voice_preparing = True
        voice = self._get_selected_voice()
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        captions = self._startup_captions if kind == "tour" else None

        def _prepare():
            ready, message = _prepare_intro_voice_cache(
                voice, self._startup_narration, key,
                sequence_kind=kind, captions=captions,
            )
            self._intro_prepared_sig.emit(ready, message)

        threading.Thread(target=_prepare, name="argus-intro-prepare", daemon=True).start()

    def _on_intro_voice_prepared(self, ready: bool, message: str):
        self._intro_voice_preparing = False
        if ready:
            self._start_first_run_intro()
        else:
            self._on_intro_playback_failed(message or "Gemini could not prepare the introduction.")

    def _start_first_run_intro(self):
        try:
            kind = self._startup_sequence_kind or "greeting"
            if kind == "tour":
                self._prepare_live_intro_widgets("tour")
                self._popup_manager.dismiss_all_popups()
            if self._overlay is not None:
                self._overlay.hide()
            self._intro_in_progress = True
            self._interaction_gated = True
            self._intro_overlay = FirstRunIntroOverlay(
                self.centralWidget(),
                duration_s=(FirstRunIntroOverlay._TOUR_DURATION_S if kind == "tour"
                            else FirstRunIntroOverlay._GREETING_DURATION_S),
                speak=True,
                voice_name=self._get_selected_voice(),
                api_key=os.environ.get("GEMINI_API_KEY", ""),
                chapters=self._startup_chapters,
                narration=self._startup_narration,
                captions=self._startup_captions,
                sequence_kind=kind,
            )
            self._intro_overlay.setGeometry(self.centralWidget().rect())
            self._intro_overlay.caption_changed.connect(self._show_intro_caption)
            self._intro_overlay.chapter_changed.connect(self._on_intro_chapter_changed)
            self._intro_overlay._speech_error.connect(self._on_intro_playback_failed)
            self._intro_overlay.finished.connect(self._on_intro_finished)
            self._intro_overlay.show()
            self._intro_overlay.raise_()
            self._intro_overlay._start_narration()
        except Exception as exc:
            traceback.print_exc()
            self._intro_terminal_report("FAILED", str(exc))
            self._on_intro_playback_failed(str(exc), report=False)

    def _intro_terminal_report(self, state: str, detail: str = ""):
        if state == "FAILED":
            self._log.append_log(f"ERR: Introduction failed: {detail}")
        elif state == "COMPLETED":
            self._log.append_log("SYS: Introduction completed.")

    def _on_intro_playback_failed(self, message: str, report: bool = True):
        overlay = getattr(self, "_intro_overlay", None)
        if overlay is not None:
            overlay.stop_speech()
            overlay.hide()
            overlay.deleteLater()
            self._intro_overlay = None
        if self._startup_sequence_kind == "tour":
            self._mission._switch_tab(0)
            self._restore_live_intro_widgets(handoff_to_comms=True)
        self._intro_in_progress = False
        self._intro_voice_preparing = False
        self._interaction_gated = False
        if self._manual_tour_replay:
            self._manual_tour_replay = False
            if self.on_tour_state_change:
                self.on_tour_state_change(False)
        if report:
            self._intro_terminal_report("FAILED", message)
        if self._pending_ready_after_intro and self._overlay is not None:
            self._overlay.set_validation_error(message)
            self._overlay.show()
            self._overlay.raise_()
            self._overlay._center_in_parent()

    def _on_intro_finished(self):
        _save_intro_settings(True, self._pending_greeting_enabled)
        if self._startup_sequence_kind == "tour":
            self._restore_live_intro_widgets(handoff_to_comms=True)
        self._intro_in_progress = False
        if self._intro_overlay is not None:
            self._intro_overlay.deleteLater()
            self._intro_overlay = None
        self._interaction_gated = False
        self._intro_terminal_report("COMPLETED")
        if self._manual_tour_replay:
            self._manual_tour_replay = False
            if self.on_tour_state_change:
                self.on_tour_state_change(False)
        if self._pending_ready_after_intro:
            self._continue_after_intro()
        else:
            self._clear_startup_backdrop()

    def _continue_after_intro(self):
        self._pending_ready_after_intro = False
        self._intro_in_progress = False
        self._intro_voice_preparing = False
        self._interaction_gated = False
        setup_overlay = self._overlay
        self._overlay = None
        if setup_overlay is not None:
            setup_overlay.hide()
            setup_overlay.deleteLater()
        self._ready = True
        self._ready_announced = True
        self._clear_startup_backdrop()
        self._show_voice_select_then_name()

    def _request_manual_tour_replay(self):
        if self._interaction_gated or self._intro_in_progress or self._intro_voice_preparing:
            return
        self._startup_sequence_kind = "tour"
        self._startup_chapters = _tour_chapters()
        self._startup_captions = tuple(item.caption for item in self._startup_chapters)
        self._startup_narration = " ".join(self._startup_captions)
        self._manual_tour_replay = True
        self._intro_in_progress = True
        self._intro_voice_preparing = True
        self._interaction_gated = True
        if self.on_tour_state_change:
            self.on_tour_state_change(True)
        self._prepare_intro_voice()

    def _show_intro_caption(self, text: str):
        self._subtitle.clear_subtitle()
        self._subtitle.set_text(str(text or ""))

    def _intro_rect_for_widget(self, widget, padding: int = 0) -> QRectF:
        if widget is None or widget.width() <= 0 or widget.height() <= 0:
            return QRectF()
        root = self.centralWidget()
        overlay = self._intro_overlay or root
        origin = widget.mapTo(root, QPointF(0, 0).toPoint())
        if overlay is not root:
            offset = overlay.geometry().topLeft()
            origin -= offset
        rect = QRectF(origin.x(), origin.y(), widget.width(), widget.height())
        return rect.adjusted(-padding, -padding, padding, padding)

    def _on_intro_chapter_changed(self, focus: str, label: str, tab_index: int):
        if tab_index >= 0 and not self._command_center_open:
            self._command_center_open = True
            self._mission.set_command_center_open(True)
            for surface in (self._header, self._left_panel, self._right_panel, self._command_bar):
                surface.show()
            self._splitter.setSizes([
                _LEFT_W, max(260, self.width() - _LEFT_W - _RIGHT_W - _NAV_W), _RIGHT_W,
            ])
        if tab_index >= 0:
            self._mission._switch_tab(tab_index)
        elif focus != "mission_tools" and self._mission._active_tab == 3:
            self._mission._switch_tab(0)
        self._intro_focus_key = focus
        if focus == "input":
            self._chat_bubble.show()
            self._chat_bubble._input.show()
        overlay = getattr(self, "_intro_overlay", None)
        if overlay is None:
            return
        widgets = {
            "core": self.hud, "subtitles": self._subtitle, "header": self._header,
            "awareness": self._left_panel, "mission_comms": self._mission,
            "mission_tasks": self._mission, "mission_assets": self._mission,
            "mission_tools": self._mission, "input": self._chat_bubble._input,
            "dock": self._footer_panel, "handoff": self._chat_bubble,
        }
        widget = widgets.get(focus, self._ai_core_wrap)
        rect = self._intro_rect_for_widget(widget, 8 if focus == "core" else 4)
        if focus == "core" and rect.isValid():
            diameter = min(rect.width(), rect.height()) * 0.62
            rect = QRectF(rect.center().x() - diameter / 2,
                          rect.center().y() - diameter / 2,
                          diameter, diameter)
        persistent = (self._intro_rect_for_widget(self._header),)
        overlay.set_spotlight(rect, label, "ellipse" if focus == "core" else "rect", persistent)

    def _prepare_live_intro_widgets(self, kind: str = "tour"):
        if not self._intro_live_groups:
            self._intro_original_tab = self._mission._active_tab
            self._intro_original_command_center = self._command_center_open
            if kind == "tour" and not self._command_center_open:
                self._command_center_open = True
                self._mission.set_command_center_open(True)
                for surface in (self._header, self._left_panel, self._right_panel, self._command_bar):
                    surface.show()
                self._splitter.setSizes([
                    _LEFT_W,
                    max(260, self.width() - _LEFT_W - _RIGHT_W - _NAV_W),
                    _RIGHT_W,
                ])
            definitions = (
                ("core", self._ai_core_wrap, 0.0, 6.0),
                ("awareness", self._left_panel, 6.0, 9.0),
                ("communications", self._right_panel, 8.8, 15.0),
                ("dock", self._footer_panel, 15.0, 18.0),
            )
            for name, widget, start, end in definitions:
                # The tour owns its opacity effects; command-center reveal animations
                # may replace Qt effects while the chapter is active.
                original_effect = None
                original_visible = widget.isVisible()
                effect = None if name == "dock" else QGraphicsOpacityEffect(widget)
                if effect is not None:
                    widget.setGraphicsEffect(effect)
                    effect.setOpacity(0.0)
                if name == "dock":
                    widget.hide()
                self._intro_live_groups.append({
                    "name": name, "widget": widget, "start": start, "end": end,
                    "effect": effect, "original_effect": original_effect,
                    "original_visible": original_visible, "completed": False,
                })
        timer = self._presence_system._presence_tmr
        self._intro_presence_was_active = timer.isActive()
        timer.stop()

    def _apply_live_intro_progress(self, seconds: float):
        position = max(0.0, float(seconds))
        for group in self._intro_live_groups:
            widget = group["widget"]
            start, end = group["start"], group["end"]
            if group["name"] == "dock":
                widget.setVisible(position >= start)
            if position >= end:
                group["completed"] = True
                if group["effect"] is not None:
                    widget.setGraphicsEffect(None)
                    group["effect"] = None
            elif position < start:
                if group["effect"] is not None:
                    group["effect"].setOpacity(0.0)
                group["completed"] = False
            elif group["effect"] is not None:
                group["effect"].setOpacity(min(1.0, max(0.01, (position - start) / max(0.01, end - start))))

    def _restore_live_intro_widgets(self, handoff_to_comms: bool = False):
        for group in self._intro_live_groups:
            widget = group["widget"]
            if widget.graphicsEffect() is not None:
                widget.setGraphicsEffect(None)
            original = group.get("original_effect")
            if original is not None:
                try:
                    widget.setGraphicsEffect(original)
                except RuntimeError:
                    widget.setGraphicsEffect(None)
            widget.setVisible(group.get("original_visible", True))
        self._intro_live_groups.clear()
        target_tab = 0 if handoff_to_comms else self._intro_original_tab
        if not getattr(self, "_intro_original_command_center", True):
            self._set_command_center(False, announce=False)
        self._mission._switch_tab(target_tab)
        if self._intro_presence_was_active:
            self._presence_system._presence_tmr.start(15000)

    def _check_and_show_name_signin(self):
        """Show the name sign-in overlay only if no name is saved in memory."""
        try:
            from memory.memory_manager import load_memory
            memory = load_memory()
            name_entry = memory.get("identity", {}).get("name")
            name = None
            if isinstance(name_entry, dict):
                name = name_entry.get("value")
            elif isinstance(name_entry, str):
                name = name_entry
            if name and name.strip():
                # Name already known — no need to ask
                return
        except Exception:
            pass
        self._show_name_signin()

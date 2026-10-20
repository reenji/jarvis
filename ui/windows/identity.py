"""Mainwindowidentity main-window behavior."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

class _MainWindowIdentityMixin:
    def _show_voice_select_then_name(self):
        """Show voice popup only on first boot (no saved voice); then chain name popup."""
        # Check if a voice has already been saved
        voice_already_set = False
        try:
            if API_FILE.exists():
                d = json.loads(API_FILE.read_text(encoding="utf-8"))
                if d.get("voice_name"):
                    voice_already_set = True
        except Exception:
            pass

        if voice_already_set:
            # Voice already chosen — skip straight to name check
            self._check_and_show_name_signin()
            return

        current = self._get_selected_voice()
        ov = VoiceSelectOverlay(self.centralWidget(), current_voice=current)
        cw = self.centralWidget()
        ow, oh = 420, 380
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )

        def _voice_done(voice_value: str):
            ov.hide()
            self._voice_overlay = None
            # Apply and persist the chosen voice
            idx = self._voice_combo.findData(voice_value)
            if idx >= 0:
                self._voice_combo.setCurrentIndex(idx)
            self._update_voice_btn()
            # Chain into name popup
            self._check_and_show_name_signin()

        ov.done.connect(_voice_done)
        ov.show()
        self._voice_overlay = ov

    def _show_name_signin(self):
        # Pre-fill with existing name if one is saved
        existing_name = ""
        try:
            from memory.memory_manager import load_memory
            memory = load_memory()
            name_entry = memory.get("identity", {}).get("name")
            if isinstance(name_entry, dict):
                existing_name = name_entry.get("value", "")
            elif isinstance(name_entry, str):
                existing_name = name_entry
        except Exception:
            pass

        # Don't open a second copy if already visible
        if self._name_overlay and self._name_overlay.isVisible():
            self._name_overlay.raise_()
            return

        ov = NameSignInOverlay(self.centralWidget(), existing_name=existing_name)
        cw = self.centralWidget()
        ow, oh = 420, 310
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_name_done)
        ov._close_btn.clicked.disconnect()
        ov._close_btn.clicked.connect(self._close_name_overlay)
        ov.show()
        self._name_overlay = ov

    def _close_name_overlay(self):
        if self._name_overlay:
            self._name_overlay.hide()
            self._name_overlay.deleteLater()
            self._name_overlay = None

    def _on_name_done(self, name: str):
        if self._name_overlay:
            self._name_overlay.hide()
            self._name_overlay.deleteLater()
            self._name_overlay = None
        if not name or not name.strip():
            # X button was pressed — don't overwrite saved name
            return
        save_name = name.strip()
        try:
            from memory.memory_manager import update_memory
            update_memory({"identity": {"name": {"value": save_name}}})
            self._log.append_log(f"SYS: Identity set — {save_name}.")
            self._log.append_log(f"ARGUS: The workshop is now at your disposal, {save_name}.")
            self._log.append_log("ARGUS: All systems nominal. How may I assist you today?")
        except Exception as e:
            self._log.append_log(f"SYS: Could not save name: {e}")
        # Notify ArgusLive so it can update the running session immediately
        if self.on_name_change:
            try:
                self.on_name_change(save_name)
            except Exception as e:
                self._log.append_log(f"SYS: Name callback error: {e}")
        # Refresh the button label to show current name
        self._update_name_btn()

    def _update_name_btn(self):
        """Update the Change Name button to show the currently saved name."""
        if not hasattr(self, "_name_btn"):
            return
        try:
            from memory.memory_manager import load_memory
            memory = load_memory()
            name_entry = memory.get("identity", {}).get("name")
            name = None
            if isinstance(name_entry, dict):
                name = name_entry.get("value")
            elif isinstance(name_entry, str):
                name = name_entry
            if name and name.strip() and name.strip().lower() not in ("sir", "madam"):
                display_name = name.strip()
                if len(display_name) > 14:
                    display_name = display_name[:13].rstrip() + "…"
                self._name_btn.setText("Nome")
                self._name_btn.setToolTip(f"Nome do operador: {display_name}")
            else:
                self._name_btn.setText("Nome")
                self._name_btn.setToolTip("Definir nome do operador")
        except Exception:
            self._name_btn.setText("Nome")

    def _show_voice_select(self):
        if self._voice_overlay and self._voice_overlay.isVisible():
            self._voice_overlay.raise_()
            return

        current = self._get_selected_voice()

        ov = VoiceSelectorOverlay(
            self.centralWidget(),
            current_provider="gemini",
            current_voice_id=current,
            current_api_key="",
        )
        cw = self.centralWidget()
        ow, oh = 520, 540
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_tts_select_done)
        ov._close_btn.clicked.disconnect()
        ov._close_btn.clicked.connect(self._close_voice_overlay)
        ov.show()
        self._voice_overlay = ov

    def _close_voice_overlay(self):
        if self._voice_overlay:
            self._voice_overlay.hide()
            self._voice_overlay.deleteLater()
            self._voice_overlay = None

    def _on_voice_select_done(self, voice_value: str):
        if hasattr(self, "_voice_overlay") and self._voice_overlay:
            self._voice_overlay.hide()
            self._voice_overlay.deleteLater()
            self._voice_overlay = None
        # Sync the hidden combo so existing voice-change logic fires
        idx = self._voice_combo.findData(voice_value)
        if idx >= 0:
            self._voice_combo.setCurrentIndex(idx)
        self._update_voice_btn()

    def _update_voice_btn(self):
        """Update the voice button label to show the currently selected voice."""
        if not hasattr(self, "_voice_btn"):
            return
        try:
            voice_val = self._get_selected_voice()
            label = VOICE_VALUE_TO_LABEL.get(voice_val, voice_val.title())
            self._voice_btn.setText(f"◈  {label.upper()}  ·  CHANGE VOICE")
        except Exception:
            self._voice_btn.setText("◈  CHANGE VOICE")

    def _load_saved_tts(self):
        """Read saved TTS config and update the button label."""
        self._update_tts_btn()

    def _show_tts_select(self):
        # Don't open a second copy if already visible
        if self._tts_overlay and self._tts_overlay.isVisible():
            self._tts_overlay.raise_()
            return

        # Read current provider + voice from JSON; API key from keychain
        provider = "gemini"
        voice_id = "orus"
        api_key  = ""
        try:
            if API_FILE.exists():
                d = json.loads(API_FILE.read_text(encoding="utf-8"))
                provider = d.get("tts_provider", "gemini")
                voice_id = d.get("tts_voice_id", "orus")
        except Exception:
            pass
        try:
            api_key = get_secret_store().get("tts_api_key") or ""
        except Exception:
            pass

        ov = VoiceSelectorOverlay(
            self.centralWidget(),
            current_provider=provider,
            current_voice_id=voice_id,
            current_api_key=api_key,
        )
        cw = self.centralWidget()
        ow, oh = 520, 540
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_tts_select_done)
        # Wire X button to also clear the reference
        ov._close_cb = self._close_tts_overlay
        ov._close_btn.clicked.disconnect()
        ov._close_btn.clicked.connect(self._close_tts_overlay)
        ov.show()
        self._tts_overlay = ov

    def _close_tts_overlay(self):
        if self._tts_overlay:
            self._tts_overlay.hide()
            self._tts_overlay.deleteLater()
            self._tts_overlay = None

    def _on_tts_select_done(self, provider: str, voice_id: str, api_key: str):
        if self._tts_overlay:
            self._tts_overlay.hide()
            self._tts_overlay.deleteLater()
            self._tts_overlay = None

        # Save API key to OS keychain — never written to disk in plain text
        if api_key:
            try:
                get_secret_store().set("tts_api_key", api_key)
            except Exception as e:
                self._log.append_log(f"SYS: Could not save TTS key to keychain: {e}")

        # Persist only non-sensitive fields to JSON
        try:
            cfg = json.loads(API_FILE.read_text(encoding="utf-8")) if API_FILE.exists() else {}
        except Exception:
            cfg = {}
        cfg["tts_provider"] = provider
        cfg["tts_voice_id"] = voice_id
        if provider == "gemini":
            cfg["voice_name"] = voice_id
            os.environ["GEMINI_VOICE_NAME"] = voice_id
        cfg.pop("tts_api_key",  None)   # scrub any legacy plain-text key
        cfg.pop("tts_preset",   None)   # scrub old preset field
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        except Exception as e:
            self._log.append_log(f"SYS: Could not save TTS config: {e}")

        # Derive a friendly label for the log
        label = voice_id
        for lbl, vid in PROVIDER_VOICES.get(provider, []):
            if vid == voice_id:
                label = lbl
                break
        self._log.append_log(f"SYS: Voice → {label}  ({provider})")
        self._update_tts_btn()
        if self._settings_overlay is not None:
            self._settings_overlay._voice_select_button.setText(f"Trocar voz · {label}")

        # Keep the hidden Gemini combo in sync (used by on_voice_change callback)
        if provider == "gemini" and hasattr(self, "_voice_combo"):
            idx = self._voice_combo.findData(voice_id)
            if idx >= 0:
                # Block the signal so we don't double-fire on_voice_change
                self._voice_combo.blockSignals(True)
                self._voice_combo.setCurrentIndex(idx)
                self._voice_combo.blockSignals(False)
            _cache_intro_voice_async(voice_id)

        if self.on_tts_provider_change:
            try:
                self.on_tts_provider_change(provider, api_key, voice_id)
            except Exception as e:
                self._log.append_log(f"SYS: TTS callback error: {e}")

    def _update_tts_btn(self):
        """Update the TTS button label to show the active voice name."""
        if not hasattr(self, "_tts_btn"):
            return
        try:
            provider = "gemini"
            voice_id = "orus"
            if API_FILE.exists():
                d = json.loads(API_FILE.read_text(encoding="utf-8"))
                provider = d.get("tts_provider", "gemini")
                voice_id = d.get("tts_voice_id", "orus")
            label = voice_id.title()
            for lbl, vid in PROVIDER_VOICES.get(provider, []):
                if vid == voice_id:
                    label = lbl
                    break
            self._tts_btn.setText(f"Voz · {label}")
            self._tts_btn.setToolTip(f"Voz do ARGUS: {label}")
        except Exception:
            self._tts_btn.setText("Voz")

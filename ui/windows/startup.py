"""Mainwindowstartup main-window behavior."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

class _MainWindowStartupMixin:
    def _restore_detached_panels(self) -> None:
        """Compatibility hook for persisted panel layouts."""

    def _start_layout_autosave(self) -> None:
        """Compatibility hook for layout persistence."""

    def _start_auto_graphics_detection(self) -> None:
        """Choose a graphics profile from basic, local hardware facts."""
        if get_graphics_mode() != "auto":
            return
        QTimer.singleShot(250, self._run_auto_graphics_detection)

    def _run_auto_graphics_detection(self) -> None:
        try:
            memory_gib = psutil.virtual_memory().total / (1024 ** 3)
            cores = psutil.cpu_count(logical=True) or 1
            quality = "low" if cores <= 4 or memory_gib < 8 else (
                "high" if cores >= 8 and memory_gib >= 16 else "medium"
            )
            facts = f"{platform.system()}|{platform.machine()}|{cores}|{memory_gib:.1f}"
            report = {
                "quality": quality,
                "fingerprint": hashlib.sha256(facts.encode()).hexdigest()[:16],
                "reason": f"Recomendado para este dispositivo ({cores} núcleos de CPU e {memory_gib:.0f} GB de RAM).",
            }
            chosen = save_auto_graphics_result(report)
            self._graphics_quality = chosen
            profile = GRAPHICS_PROFILES[chosen]
            self.hud.set_graphics_quality(chosen)
            self._ai_canvas.set_graphics_quality(chosen)
            if self._vision_preview is not None:
                self._vision_preview.set_graphics_quality(chosen)
            self._metric_tmr.setInterval(int(profile["metrics_ms"]))
            if self._settings_overlay and self._settings_overlay.isVisible():
                self._settings_overlay.set_auto_graphics_result(chosen, report["reason"])
        except (OSError, RuntimeError, ValueError, AttributeError):
            # Keep the last valid profile if this machine does not expose facts.
            return

    def _finish_auto_graphics_detection(self, report: dict) -> None:
        if get_graphics_mode() != "auto":
            return
        quality = save_auto_graphics_result(report)
        self._apply_graphics_quality_live(quality)
        settings = _read_ui_settings()
        settings["graphics_quality_mode"] = "auto"
        UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        if self._settings_overlay and self._settings_overlay.isVisible():
            self._settings_overlay.set_auto_graphics_result(
                quality, str(report.get("reason", "Recomendado para este dispositivo."))
            )

    def __init__(self, face_path: str):
        super().__init__()
        _load_bundled_fonts()
        self.setWindowTitle("J.A.R.V.I.S — MARK XXXIX")
        self.setMinimumSize(_MIN_W, _MIN_H)

        # Set dark palette so no white leaks through any unstyled widget
        from PyQt6.QtGui import QColor, QPalette
        _pal = self.palette()
        _pal.setColor(QPalette.ColorRole.Window, QColor(C.BG))
        _pal.setColor(QPalette.ColorRole.WindowText, QColor(C.WHITE))
        _pal.setColor(QPalette.ColorRole.Base, QColor(C.DARK))
        _pal.setColor(QPalette.ColorRole.AlternateBase, QColor(C.DARK2))
        _pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(C.DARK2))
        _pal.setColor(QPalette.ColorRole.ToolTipText, QColor(C.WHITE))
        _pal.setColor(QPalette.ColorRole.Text, QColor(C.WHITE))
        _pal.setColor(QPalette.ColorRole.Button, QColor(C.DARK2))
        _pal.setColor(QPalette.ColorRole.ButtonText, QColor(C.WHITE))
        _pal.setColor(QPalette.ColorRole.BrightText, QColor(C.WHITE))
        _pal.setColor(QPalette.ColorRole.Highlight, QColor(C.PRI))
        _pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C.BG))
        self.setPalette(_pal)

        screen = QApplication.primaryScreen().availableGeometry()
        window_w = min(_DEFAULT_W, max(_MIN_W, screen.width()))
        window_h = min(_DEFAULT_H, max(_MIN_H, screen.height()))
        self.resize(window_w, window_h)
        self.move(
            screen.x() + max(0, (screen.width() - window_w) // 2),
            screen.y() + max(0, (screen.height() - window_h) // 2),
        )

        self.on_text_command        = None
        self.on_voice_change        = None
        self.on_voice_preferences_change = None
        self.on_name_change         = None
        self.on_tts_provider_change = None
        self.on_quit_requested      = None
        self._muted                 = False
        self._current_file: str | None = None
        self._tts_overlay: TTSProviderOverlay | None = None
        self._compact_mode          = False
        self._compact_widget: CompactModeWidget | None = None
        self._shortcuts_overlay: ShortcutsOverlay | None = None
        self._settings_overlay: SettingsOverlay | None = None
        self._vision_preview: VisionPreviewWindow | None = None
        self._force_quit            = False
        self._command_center_open   = False
        self._graphics_quality      = get_graphics_quality()
        self._settings_overlay = None

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {C.BG}; }}
            QTextEdit, QPlainTextEdit, QTextBrowser {{
                background: {C.DARK};
                color: {C.WHITE};
                border: none;
            }}
        """)
        central = QWidget()
        central.setObjectName("argusRoot")
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setSpacing(TOKENS.spacing["legacy_0"])
        self._header = self._build_header()
        root.addWidget(self._header)
        self._style_header()

        # Keep the previous live hardware view hidden for API compatibility;
        # the new navigation rail stays quiet until the operator asks for a panel.
        self._legacy_metrics_panel = self._build_legacy_overview()
        self._legacy_metrics_panel.setParent(central)
        self._legacy_metrics_panel.hide()
        self._left_panel = self._build_left_panel()
        self._right_panel = self._build_right_panel()

        # ── AI Core area: HudCanvas, AI Activity Canvas, Subtitles ─────────────────────
        self._ai_core_wrap = QWidget()
        self._ai_core_wrap.setObjectName("aiCore")
        self._ai_core_wrap.setStyleSheet(f"background: {C.BG};")
        ai_core_lay = QVBoxLayout(self._ai_core_wrap)
        ai_core_lay.setContentsMargins(
            TOKENS.spacing["lg"], TOKENS.spacing["legacy_18"],
            TOKENS.spacing["lg"], TOKENS.spacing["lg"],
        )
        ai_core_lay.setSpacing(TOKENS.spacing["md"])

        # Preserve the existing HUD API for the client and integrations while
        # using a calmer, state-driven orb in the new presentation.
        self.hud = HudCanvas(face_path, config=HudConfig())
        self.hud.hide()
        self.hud._tmr.stop()
        self.hud.setParent(central)
        from ui.hud.orb import ActivityVisualizer, ReactorOrb
        from ui.motion import resolve_reduced_motion
        motion_preference = str(_read_ui_settings().get("motion_preference", "system"))
        self._motion_preference = motion_preference
        self._reduced_motion = resolve_reduced_motion(motion_preference)
        self._orb = ReactorOrb(
            graphics_quality=self._graphics_quality,
            reduced_motion=self._reduced_motion,
            parent=self._ai_core_wrap,
        )
        self._orb.setMinimumSize(216, 216)
        self._orb.setMaximumSize(320, 320)
        self._core_title = QLabel("ARGUS")
        self._core_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._core_title.setFont(QFont(UI_FONT, TOKENS.font_sizes["title"], QFont.Weight.DemiBold))
        self._core_title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        ai_core_lay.addWidget(self._core_title)
        ai_core_lay.addStretch(1)
        ai_core_lay.addWidget(self._orb, alignment=Qt.AlignmentFlag.AlignHCenter, stretch=5)
        self._core_state = QLabel("◇  Em espera")
        self._core_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._core_state.setAccessibleName("Estado atual do ARGUS")
        self._core_state.setFont(QFont(UI_FONT, TOKENS.font_sizes["section"], QFont.Weight.DemiBold))
        ai_core_lay.addWidget(self._core_state)
        self._error_guidance = QLabel(
            "O cliente sinalizou um erro. Consulte Logs para identificar a causa antes de tentar novamente."
        )
        self._error_guidance.setAccessibleName("Orientação para recuperar de um erro")
        self._error_guidance.setWordWrap(True)
        self._error_guidance.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_guidance.setFont(QFont(UI_FONT, TOKENS.font_sizes["caption"]))
        self._error_guidance.setStyleSheet(
            f"color: {C.TEXT_MED}; background: {C.PANEL}; "
            f"border-left: 2px solid {C.RED}; border-radius: {TOKENS.radii['sm']}px; "
            f"padding: {TOKENS.spacing['sm']}px;"
        )
        self._error_guidance.hide()
        ai_core_lay.addWidget(self._error_guidance)
        visualizer_row = QHBoxLayout()
        visualizer_row.addStretch()
        self._activity_visualizer = ActivityVisualizer(
            graphics_quality=self._graphics_quality,
            reduced_motion=self._reduced_motion,
            parent=self._ai_core_wrap,
        )
        self._activity_visualizer.setFixedSize(176, 32)
        visualizer_row.addWidget(self._activity_visualizer)
        visualizer_row.addStretch()
        ai_core_lay.addLayout(visualizer_row)
        activity_hint = QLabel("Atividade visual · nível de áudio não medido")
        activity_hint.setAccessibleName("Atividade visual, sem nível de áudio medido")
        activity_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        activity_hint.setWordWrap(True)
        activity_hint.setFont(QFont(UI_FONT, TOKENS.font_sizes["caption"]))
        activity_hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        ai_core_lay.addWidget(activity_hint)
        ai_core_lay.addStretch(1)

        self._research_progress = ResearchProgressWidget(parent=self._ai_core_wrap)
        ai_core_lay.addWidget(self._research_progress, stretch=0)

        self._presentation_progress = ResearchProgressWidget(
            parent=self._ai_core_wrap,
            task_title="APRESENTAÇÃO",
            accessible_name="Progresso da apresentação",
        )
        ai_core_lay.addWidget(self._presentation_progress, stretch=0)

        # AI Activity Canvas removed for cleaner layout
        self._ai_canvas = AIActivityCanvas(config=AIActivityConfig())
        self._ai_canvas.hide()
        if hasattr(self._ai_canvas, "_tmr"):
            self._ai_canvas._tmr.stop()

        # Subtitles — enhanced with speaker labels
        self._subtitle = _SubtitleWidget(parent=self._ai_core_wrap)
        self._subtitle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ai_core_lay.addWidget(self._subtitle, stretch=0)

        self._focus_dialogue = FocusDialogueWidget(parent=self._ai_core_wrap)
        self._focus_dialogue.command_submitted.connect(self._send)
        ai_core_lay.addWidget(self._focus_dialogue, stretch=0)
        self._transcript_panel = self._build_transcript_panel()
        self._chat_bubble._sig.connect(self._focus_dialogue.append_log)
        self._mission.log_widget.append_log("SYS: A sessão atual está pronta para mensagens.")

        # Conversation, central reactor, and current execution share the window.
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._transcript_panel)
        self._splitter.addWidget(self._ai_core_wrap)
        self._splitter.addWidget(self._right_panel)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([
            _LEFT_W, max(260, self.width() - _LEFT_W - _RIGHT_W - _NAV_W), _RIGHT_W,
        ])
        self._splitter.setCollapsible(0, True)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, True)
        self._splitter.setHandleWidth(6)
        self._style_splitter()

        workspace = QWidget()
        self._middle_section = workspace
        workspace.setObjectName("desktopWorkspace")
        workspace.setStyleSheet(f"background: {C.BG};")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(*([TOKENS.spacing["legacy_0"]] * 4))
        workspace_layout.setSpacing(TOKENS.spacing["legacy_0"])
        workspace_layout.addWidget(self._left_panel)
        workspace_layout.addWidget(self._splitter, stretch=1)
        root.addWidget(workspace, stretch=1)
        # ── Tool progress indicator (above footer) ──────────────────────────
        self._tool_progress = ToolProgressWidget()
        root.addWidget(self._tool_progress)

        self._command_bar = self._build_footer()
        self._footer_panel = self._command_bar
        root.addWidget(self._command_bar)

        # Persistent maker's mark: remains visible in both Focus View and the
        # expanded Command Center without reading as application status.
        self._maker_signature = self._build_maker_signature()
        root.addWidget(self._maker_signature)
        self._command_center_open = True
        self._set_command_center(True, announce=False)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metric update timer
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(int(GRAPHICS_PROFILES[self._graphics_quality]["metrics_ms"]))
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._log_sig.connect(self._mission.log_widget.append_log)
        self._log_sig.connect(self._append_compact_log)
        self._state_sig.connect(self._apply_state)
        self._voice_sig.connect(self._sync_voice_combo)
        self._sub_sig.connect(self._subtitle.set_text)
        self._sub_clear_sig.connect(self._subtitle.clear_subtitle)
        self._sub_hold_sig.connect(self._subtitle.start_hold_timer)
        self._mode_sig.connect(self._ai_canvas.set_mode)
        self._task_sig.connect(self._mission.task_widget.push_task)
        self._tool_sig.connect(self._mission.tool_widget.push)
        self._theme_sig.connect(ThemeManager.set_theme)
        self._graphics_sig.connect(self._apply_graphics_quality_live)
        self._vision_preview_sig.connect(self._show_vision_preview)
        self._vision_preview_hide_sig.connect(self._hide_vision_preview)
        self._research_progress_sig.connect(lambda update: self._research_progress.update_progress(**update))
        self._research_progress_finish_sig.connect(self._research_progress.finish)
        self._research_progress_hide_sig.connect(self._research_progress.dismiss)
        self._presentation_progress_sig.connect(
            lambda update: self._presentation_progress.update_progress(**update)
        )
        self._presentation_progress_finish_sig.connect(self._presentation_progress.finish)
        self._presentation_progress_hide_sig.connect(self._presentation_progress.dismiss)
        self._ui_command_sig.connect(self._handle_ui_command)
        self._intro_prepared_sig.connect(self._on_intro_voice_prepared)
        tab_order = [
            *self._nav_buttons,
            self._chat_bubble._input,
            self._mute_btn,
            self._tts_btn,
            self._name_btn,
            self._theme_btn,
            self._mission._tabs[1],
            self._mission._tabs[3],
            self._mission._tabs[0],
            self._mission._tabs[2],
            self._nav_settings_btn,
            self._utility_btn,
        ]
        for current, following in zip(tab_order, tab_order[1:]):
            self.setTabOrder(current, following)
        self._apply_state("IDLE")

        # ── Popup System Initialization ────────────────────────────────────────
        self._popup_manager = PopupManager(self._ai_core_wrap)
        self._presence_system = PresenceSystem(self._popup_manager)
        # Context mode tracking
        self._context_mode = "idle"
        self._session_start = time.time()

        self._overlay: SetupOverlay | None = None
        self._name_overlay: NameSignInOverlay | None = None
        self._voice_overlay: VoiceSelectOverlay | None = None
        self._tts_overlay: TTSProviderOverlay | None = None
        self.on_voice_change = None
        self.on_voice_preferences_change = None
        self.on_tts_provider_change = None
        self._load_saved_voice()
        self._load_saved_tts()

        # ── System tray integration ──────────────────────────────────────────
        self._setup_system_tray()

        # ── Theme manager listener ───────────────────────────────────────────
        ThemeManager.add_listener(self._on_theme_changed)
        # Load saved theme on boot
        try:
            from pathlib import Path
            import json
            cfg_file = Path.home() / ".argus" / "config" / "settings.json"
            if cfg_file.exists():
                cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                saved_theme = cfg.get("theme", "")
                if saved_theme and saved_theme in ThemeManager.theme_names():
                    ThemeManager.set_theme(saved_theme)
        except Exception:
            pass

        # Every key source uses the same Gemini verification gate. Environment
        # variables and remembered keys are never trusted merely because they
        # were present on an earlier run.
        self._ready = False
        completed, greeting_enabled = _load_intro_settings()
        self._intro_should_play = not completed or greeting_enabled
        self._startup_sequence_kind = "tour" if not completed else ("greeting" if greeting_enabled else "")
        self._startup_chapters: tuple[IntroChapter, ...] = ()
        self._startup_captions: tuple[str, ...] = ()
        self._startup_narration = ""
        self._intro_overlay: FirstRunIntroOverlay | None = None
        self._intro_focus_key = ""
        self._intro_in_progress = False
        self._intro_voice_preparing = False
        self._interaction_gated = True
        self._manual_tour_replay = False
        self._pending_ready_after_intro = False
        self._pending_greeting_enabled = greeting_enabled
        self._ready_announced = False
        self._intro_live_groups: list[dict] = []
        self._intro_original_tab = 0
        self._intro_presence_was_active = False
        self.on_tour_state_change = None
        candidate_key = os.environ.get("GEMINI_API_KEY", "").strip()
        candidate_is_saved = False
        try:
            if not candidate_key:
                store = get_secret_store()
                saved = store.get("gemini_api_key")
                if saved:
                    candidate_key = saved.strip()
                    candidate_is_saved = True
        except Exception:
            candidate_key = ""
            candidate_is_saved = False

        self._show_setup()
        self._start_auto_graphics_detection()
        if candidate_key and self._overlay:
            self._overlay.validate_candidate(
                candidate_key,
                remember_key=candidate_is_saved,
                purge_saved_on_failure=candidate_is_saved,
            )

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_min = QShortcut(QKeySequence(Qt.Key.Key_F6), self)
        sc_min.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_min.activated.connect(lambda: _minimize_or_restore(self))

        # New shortcuts
        sc_help = QShortcut(QKeySequence("Ctrl+/"), self)
        sc_help.activated.connect(self._toggle_shortcuts_overlay)
        sc_compact = QShortcut(QKeySequence("Ctrl+M"), self)
        sc_compact.activated.connect(self._toggle_compact_mode)
        sc_theme = QShortcut(QKeySequence("Ctrl+Shift+T"), self)
        sc_theme.activated.connect(self._cycle_theme)
        sc_command = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        sc_command.activated.connect(
            lambda: self._set_command_center(not self._command_center_open)
        )
        sc_esc = QShortcut(QKeySequence("Escape"), self)
        sc_esc.activated.connect(self._dismiss_overlays)

        # Shortcuts to show panel content as popups
        sc_show_left = QShortcut(QKeySequence("L"), self)
        sc_show_left.activated.connect(self._show_left_panel_popup)
        sc_show_right = QShortcut(QKeySequence("R"), self)
        sc_show_right.activated.connect(self._show_right_panel_popup)

    def closeEvent(self, event):
        # Minimize to tray instead of quitting (if tray is available)
        try:
            if hasattr(self, "_tray") and self._tray.isVisible() and not getattr(self, "_force_quit", False):
                event.ignore()
                if self._vision_preview is not None:
                    self._vision_preview.stop()
                self.hide()
                self._tray.showMessage(
                    "ARGUS", "Running in background. Click tray icon to restore.",
                    QSystemTrayIcon.MessageIcon.Information, 2000
                )
                return
        except Exception:
            pass
        if self._vision_preview is not None:
            self._vision_preview.stop()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _setup_system_tray(self):
        self._force_quit = False
        self._tray = QSystemTrayIcon(self)
        # Create a simple icon programmatically
        px = QPixmap(32, 32)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(qcol(C.PRI), 2))
        p.drawEllipse(4, 4, 24, 24)
        p.setBrush(QBrush(qcol(C.ENERGY)))
        p.drawEllipse(10, 10, 12, 12)
        p.end()
        self._tray.setIcon(QIcon(px))
        self._tray.setToolTip("J.A.R.V.I.S — MARK XXXIX")

        tray_menu = QMenu()
        tray_menu.setStyleSheet(f"""
            QMenu {{
                background: {C.PANEL}; color: {C.WHITE};
                border: 1px solid {C.BORDER};
            }}
            QMenu::item:selected {{ background: {C.PRI_GHO}; color: {C.PRI}; }}
        """)

        show_action = QAction("Show ARGUS", self)
        show_action.triggered.connect(self._tray_show)
        tray_menu.addAction(show_action)

        mute_action = QAction("Toggle Mute", self)
        mute_action.triggered.connect(self._toggle_mute)
        tray_menu.addAction(mute_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit ARGUS", self)
        quit_action.triggered.connect(self._tray_quit)
        tray_menu.addAction(quit_action)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _tray_show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_quit(self):
        self._request_quit()

    def _request_quit(self):
        """Use one clean shutdown path for tray, UI, and ARGUS self-quit."""
        self._force_quit = True
        try:
            if self.on_quit_requested:
                self.on_quit_requested()
        except Exception as exc:
            self._log.append_log(f"ERR: Shutdown cleanup — {exc}")
        try:
            if hasattr(self, "_tray"):
                self._tray.hide()
        except Exception:
            pass
        self.close()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._tray_show()

    def _toggle_compact_mode(self):
        if self._compact_mode:
            # Restore from compact
            if self._compact_widget:
                self._compact_widget.close_without_restore()
                self._compact_widget.deleteLater()
                self._compact_widget = None
            self.showNormal()
            self.raise_()
            self._compact_mode = False
        else:
            # Enter compact mode
            self._compact_mode = True
            self.hide()
            cw = CompactModeWidget(
                on_send=self._send,
                on_mute=self._toggle_mute,
                graphics_quality=self._graphics_quality,
                reduced_motion=self._reduced_motion,
                muted=self._muted,
            )
            cw.expand_requested.connect(self._toggle_compact_mode)
            screen = QApplication.primaryScreen().availableGeometry()
            cw.move(
                screen.x() + max(0, (screen.width() - cw.width()) // 2),
                screen.y() + max(0, (screen.height() - cw.height()) // 2),
            )
            cw.show()
            self._compact_widget = cw
            cw.set_state(getattr(self.hud, "state", "IDLE"))

    def _append_compact_log(self, message: str):
        if self._compact_widget is not None:
            self._compact_widget.append_log(message)

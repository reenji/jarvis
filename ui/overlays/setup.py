"""First-run setup and Gemini API-key onboarding overlay."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, bool)
    validation_finished = pyqtSignal(bool, str, str, bool)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C.BG))
        p.end()
        super().paintEvent(event)

    def __init__(self, parent=None, replay_every_launch: bool = False):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER_B};
                border-radius: {TOKENS.radii['legacy_6']}px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected
        self._validation_pending = False
        self._purge_saved_on_failure = False
        self._verified_key = ""
        self.validation_finished.connect(self._on_validation_finished)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing["legacy_30"], TOKENS.spacing["legacy_22"], TOKENS.spacing["legacy_30"], TOKENS.spacing["legacy_22"])
        layout.setSpacing(TOKENS.spacing["legacy_8"])

        def _lbl(txt, font_size=TOKENS.font_sizes["legacy_9"], bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont(TECH_FONT, font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", TOKENS.font_sizes["legacy_13"], True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", TOKENS.font_sizes["legacy_9"], color=C.PRI_DIM))
        layout.addSpacing(TOKENS.spacing["legacy_6"])

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(TOKENS.spacing["legacy_4"])

        layout.addWidget(_lbl("GEMINI API KEY", TOKENS.font_sizes["legacy_8"], color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("Paste Gemini API key")
        self._key_input.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_10"]))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.DARK}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_3']}px; padding: {TOKENS.spacing['legacy_4']}px {TOKENS.spacing['legacy_8']}px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)

        self._validation_lbl = QLabel("Only a verified Gemini key will be accepted.")
        self._validation_lbl.setWordWrap(True)
        self._validation_lbl.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_8"]))
        self._validation_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._validation_lbl)
        self._setup_status = QLabel("Enter a verified key to continue.")
        self._setup_status.setWordWrap(True)
        self._setup_status.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_8"]))
        self._setup_status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        layout.addWidget(self._setup_status)

        self._guide_button = QPushButton("How do I get a Gemini API key?")
        self._guide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._guide_button.setAccessibleName("Show Gemini API key guide")
        self._guide_button.clicked.connect(self._toggle_api_guide)
        layout.addWidget(self._guide_button)
        self._guide_scroll = QScrollArea()
        self._guide_scroll.setWidgetResizable(True)
        self._guide_scroll.setMaximumHeight(104)
        self._guide_scroll.setVisible(False)
        guide_body = QWidget()
        guide_layout = QVBoxLayout(guide_body)
        guide_layout.setContentsMargins(TOKENS.spacing["legacy_0"], TOKENS.spacing["legacy_0"], TOKENS.spacing["legacy_0"], TOKENS.spacing["legacy_0"])
        guide_layout.setSpacing(TOKENS.spacing["legacy_4"])
        guide = QLabel(
            "1. Open Google AI Studio and sign in.\n"
            "2. Create an API key for your project.\n"
            "3. Copy it here; ARGUS verifies it before continuing."
        )
        guide.setWordWrap(True)
        guide.setStyleSheet(f"color: {C.TEXT_MED}; background: {C.DARK}; padding: {TOKENS.spacing['legacy_8']}px;")
        guide_layout.addWidget(guide)
        self._api_key_link = QPushButton("Open Google AI Studio")
        self._api_key_link.setAccessibleName("Open Google AI Studio API key page")
        self._api_key_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._api_key_link.clicked.connect(self._open_api_key_page)
        guide_layout.addWidget(self._api_key_link)
        self._guide_scroll.setWidget(guide_body)
        layout.addWidget(self._guide_scroll)
        layout.addSpacing(TOKENS.spacing["legacy_8"])

        self._remember_key = QPushButton("☆  Remember API key on this machine")
        self._remember_key.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_7"]))
        self._remember_key.setFixedHeight(28)
        self._remember_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remember_key.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_3']}px;
                text-align: left; padding-left: {TOKENS.spacing['legacy_10']}px;
            }}
            QPushButton:hover {{
                color: {C.TEXT}; border: 1px solid {C.BORDER_B};
            }}
        """)
        self._remember_key.clicked.connect(self._toggle_remember_key)
        layout.addWidget(self._remember_key)

        self._replay_intro = QCheckBox("Play greeting at startup")
        self._replay_intro.setFixedHeight(22)
        self._replay_intro.setChecked(bool(replay_every_launch))
        self._replay_intro.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._replay_intro)

        self._skip_first_tour = QCheckBox("Pular visita guiada no primeiro uso")
        self._skip_first_tour.setAccessibleName("Pular visita guiada no primeiro uso")
        self._skip_first_tour.setFixedHeight(24)
        self._skip_first_tour.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        layout.addWidget(self._skip_first_tour)

        layout.addSpacing(TOKENS.spacing["legacy_12"])

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(TOKENS.spacing["legacy_4"])

        layout.addWidget(_lbl("OPERATING SYSTEM", TOKENS.font_sizes["legacy_8"], color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", TOKENS.font_sizes["legacy_8"], color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(TOKENS.spacing["legacy_6"])
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","☰  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_9"], QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(TOKENS.spacing["legacy_12"])

        self._init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        self._init_btn.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_10"], QFont.Weight.Bold))
        self._init_btn.setFixedHeight(36)
        self._init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: {TOKENS.radii['legacy_3']}px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        self._init_btn.clicked.connect(self._submit)
        layout.addWidget(self._init_btn)

    def showEvent(self, event):
        super().showEvent(event)
        self._center_in_parent()
        QTimer.singleShot(0, self._center_in_parent)

    def _center_in_parent(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(0, (parent.width() - self.width()) // 2),
                      max(0, (parent.height() - self.height()) // 2))

    def replay_intro_enabled(self) -> bool:
        return self._replay_intro.isChecked()

    def skip_first_tour_enabled(self) -> bool:
        return self._skip_first_tour.isChecked()

    def _toggle_api_guide(self):
        expanded = not self._guide_scroll.isVisible()
        self._guide_scroll.setVisible(expanded)
        self._guide_button.setText("Hide API key guide" if expanded else "How do I get a Gemini API key?")
        self._guide_button.setAccessibleName("Hide Gemini API key guide" if expanded else "Show Gemini API key guide")
        self._center_in_parent()

    def _open_api_key_page(self):
        QDesktopServices.openUrl(QUrl("https://aistudio.google.com/apikey"))

    def set_validating(self):
        self._validation_pending = True
        self._key_input.setEnabled(False)
        self._init_btn.setEnabled(False)
        self._setup_status.setText("VALIDATING GEMINI API KEY…")
        self._setup_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")

    def set_validation_error(self, message: str):
        self._validation_pending = False
        self._key_input.setEnabled(True)
        self._init_btn.setEnabled(True)
        self._init_btn.show()
        self._setup_status.setText("API KEY VALIDATION FAILED. Check the key and try again.")
        self._setup_status.setToolTip(str(message))
        self._validation_lbl.setText(str(message))
        self._validation_lbl.setStyleSheet(f"color: {C.RED}; background: transparent;")

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,C.DARK2),"mac":(C.ACC2,C.DARK),"linux":(C.GREEN,C.DARK)}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: {TOKENS.radii['legacy_3']}px;
                        font-weight: {TOKENS.font_weights['bold']};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.DARK}; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_3']}px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _toggle_remember_key(self):
        # Simple visual toggle; actual persistence logic lives in _on_setup_done
        # in MainWindow.
        try:
            cur = self._remember_enabled
        except AttributeError:
            self._remember_enabled = False
            cur = False

        self._remember_enabled = not cur
        if self._remember_enabled:
            self._remember_key.setText("★  Remember API key on this machine")
            self._remember_key.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.GREEN_D};
                    border: 1px solid {C.GREEN_D}; border-radius: {TOKENS.radii['legacy_3']}px;
                    text-align: left; padding-left: {TOKENS.spacing['legacy_10']}px;
                }}
                QPushButton:hover {{ color: {C.GREEN}; border: 1px solid {C.GREEN}; }}
            """)
        else:
            self._remember_key.setText("☆  Remember API key on this machine")
            self._remember_key.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_3']}px;
                    text-align: left; padding-left: {TOKENS.spacing['legacy_10']}px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() + f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        remember = bool(getattr(self, '_remember_enabled', False))
        self.validate_candidate(key, remember_key=remember)

    def validate_candidate(
        self,
        key: str,
        remember_key: bool = False,
        purge_saved_on_failure: bool = False,
    ):
        """Verify a key with Gemini without blocking the interface."""
        if self._validation_pending:
            return
        from core.api_key_validator import normalize_gemini_api_key

        normalized = normalize_gemini_api_key(key)
        self._key_input.setText(normalized)
        self._validation_pending = True
        self._purge_saved_on_failure = purge_saved_on_failure
        self._init_btn.setEnabled(False)
        self._init_btn.setText("VERIFYING WITH GEMINI…")
        self._validation_lbl.setText("Contacting Gemini. The key will not be saved unless verification succeeds.")
        self._validation_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        self.set_validating()

        def _validate():
            from core.api_key_validator import validate_gemini_api_key
            result = validate_gemini_api_key(normalized)
            self.validation_finished.emit(result.valid, result.message, normalized, remember_key)

        threading.Thread(target=_validate, daemon=True).start()

    def _on_validation_finished(self, valid: bool, message: str, key: str, remember_key: bool):
        self._validation_pending = False
        self._init_btn.setEnabled(True)
        self._init_btn.setText("▸  INITIALISE SYSTEMS")

        if not valid:
            if os.environ.get("GEMINI_API_KEY", "").strip() == key:
                os.environ.pop("GEMINI_API_KEY", None)
            self.set_validation_error(message)
            self._key_input.setStyleSheet(f"""
                QLineEdit {{
                    background: {C.DARK}; color: {C.TEXT};
                    border: 1px solid {C.RED}; border-radius: {TOKENS.radii['legacy_3']}px; padding: {TOKENS.spacing['legacy_4']}px {TOKENS.spacing['legacy_8']}px;
                }}
                QLineEdit:focus {{ border: 1px solid {C.RED}; }}
            """)
            self._key_input.setFocus()
            return

        self._validation_lbl.setText("Gemini key verified.")
        self._validation_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        self._setup_status.setText("API KEY VERIFIED")
        self._setup_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        self._verified_key = key
        self.done.emit(key, self._sel_os, remember_key)

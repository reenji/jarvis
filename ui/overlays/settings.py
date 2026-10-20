"""Shortcut, graphics, and settings overlays."""

from __future__ import annotations

import importlib

_runtime = importlib.import_module("ui._runtime")
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith("__")})

from .base import _OverlayBase

class ShortcutsOverlay(_OverlayBase):
    """Displays all keyboard shortcuts in a styled grid."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Atalhos de teclado")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ShortcutsOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER_B};
                border-radius: {TOKENS.radii['legacy_8']}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing["legacy_28"], TOKENS.spacing["legacy_22"], TOKENS.spacing["legacy_28"], TOKENS.spacing["legacy_22"])
        layout.setSpacing(TOKENS.spacing["legacy_8"])

        def _lbl(txt, size=TOKENS.font_sizes["legacy_9"], bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont(UI_FONT, size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setWordWrap(True)
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  Atalhos de teclado", TOKENS.font_sizes["legacy_13"], True))
        layout.addSpacing(TOKENS.spacing["legacy_4"])

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        layout.addWidget(sep)
        layout.addSpacing(TOKENS.spacing["legacy_6"])

        shortcuts = [
            ("F4",       "Silenciar ou ativar o microfone"),
            ("F6",       "Minimizar ou restaurar a janela"),
            ("F11",      "Alternar tela cheia"),
            ("Ctrl+/",   "Abrir esta ajuda"),
            ("Ctrl+M",   "Alternar modo compacto"),
            ("Ctrl+Shift+T", "Alternar tema de cores"),
            ("Enter",    "Enviar mensagem no campo de texto"),
            ("Esc",      "Fechar painel ou dispensar aviso"),
        ]

        for key, desc in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(TOKENS.spacing["legacy_10"])

            key_lbl = QLabel(key)
            key_lbl.setFixedWidth(80)
            key_lbl.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_9"], QFont.Weight.Bold))
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            key_lbl.setStyleSheet(f"""
                color: {C.PRI}; background: {C.PRI_GHO};
                border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_3']}px;
                padding: {TOKENS.spacing['legacy_2']}px {TOKENS.spacing['legacy_6']}px;
            """)
            row.addWidget(key_lbl)

            desc_lbl = QLabel(desc)
            desc_lbl.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_9"]))
            desc_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
            row.addWidget(desc_lbl, stretch=1)

            layout.addLayout(row)

        layout.addSpacing(TOKENS.spacing["legacy_8"])
        layout.addWidget(_lbl("Pressione Esc ou Ctrl+/ para fechar", TOKENS.font_sizes["legacy_7"], color=C.TEXT_DIM))

        self._setup_overlay_base(close_callback=self.hide)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        super().keyPressEvent(event)


class GraphicsQualityCard(QPushButton):
    """Compact, theme-aware graphics option used by Settings."""

    _COPY = {
        "auto": ("AUTO", "Recomendado", "neste dispositivo"),
        "low": ("BAIXA", "20 FPS", "menos detalhes"),
        "medium": ("MÉDIA", "30 FPS", "equilibrada"),
        "high": ("ALTA", "60 FPS", "detalhe máximo"),
    }

    def __init__(self, quality: str, parent=None):
        super().__init__(parent)
        self.quality = quality
        title, fps, detail = self._COPY[quality]
        self.setText("")
        quality_label = {"auto": "automática", "low": "baixa", "medium": "média", "high": "alta"}[quality]
        self.setAccessibleName(f"Qualidade gráfica {quality_label}")
        self.setToolTip(f"{fps} · {detail}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(88, 92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing["legacy_12"], TOKENS.spacing["legacy_10"], TOKENS.spacing["legacy_12"], TOKENS.spacing["legacy_10"])
        layout.setSpacing(TOKENS.spacing["legacy_5"])
        self._title = QLabel(title, self)
        self._title.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_9"], QFont.Weight.DemiBold))
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._title)

        self._fps = QLabel(fps, self)
        self._fps.setFont(QFont(TECH_FONT, TOKENS.font_sizes["legacy_8"], QFont.Weight.Medium))
        self._detail = QLabel(detail, self)
        self._desc = self._detail
        self._detail.setWordWrap(True)
        self._detail.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_8"], QFont.Weight.Normal))
        for label in (self._fps, self._detail):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._fps)
        layout.addWidget(self._detail, stretch=1)
        self.refresh_theme(False)

    def refresh_theme(self, selected: bool):
        if selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PRI_GHO};
                    border: 2px solid {C.PRI}; border-radius: {TOKENS.radii['legacy_6']}px;
                }}
                QPushButton:hover {{ background: {C.PANEL2}; }}
                QPushButton:focus {{ border: 2px solid {C.PRI}; }}
            """)
            self._title.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
            self._fps.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
            self._detail.setStyleSheet(f"color: {C.WHITE_DIM}; background: transparent; border: none;")
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {C.DARK};
                    border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_6']}px;
                }}
                QPushButton:hover {{ border-color: {C.BORDER_B}; background: {C.PANEL2}; }}
                QPushButton:focus {{ border: 2px solid {C.PRI}; }}
            """)
            self._title.setStyleSheet(f"color: {C.WHITE_DIM}; background: transparent; border: none;")
            self._fps.setStyleSheet(f"color: {C.WHITE_DIM}; background: transparent; border: none;")
            self._detail.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")


class SettingsOverlay(_OverlayBase):
    """Unified settings panel for identity, theme, and graphics."""

    voice_changed = pyqtSignal(str, str, str)  # provider, voice_id, api_key
    voice_selector_requested = pyqtSignal()
    voice_preferences_changed = pyqtSignal(str, int)
    name_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    graphics_changed = pyqtSignal(str)
    graphics_mode_changed = pyqtSignal(str)
    motion_preference_changed = pyqtSignal(str)
    intro_replay_changed = pyqtSignal(bool)
    tour_replay_requested = pyqtSignal()

    def __init__(self, parent=None, current_name: str = "",
                 current_voice: str = "puck", current_response_style: str = "balanced",
                 current_vad_silence_ms: int = 700, current_theme: str = "arc_reactor",
                 current_graphics: str = "medium", current_graphics_mode: str = "manual",
                 replay_intro: bool = False,
                 current_motion_preference: str = "system"):
        super().__init__(parent)
        self.setAccessibleName("Configurações do ARGUS")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SettingsOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER_B};
                border-radius: {TOKENS.radii['legacy_8']}px;
            }}
        """)

        self._current_name = current_name
        self._current_voice = current_voice
        self._current_theme = current_theme
        self._current_graphics = _normalize_graphics_quality(current_graphics)
        self._current_graphics_mode = current_graphics_mode if current_graphics_mode in {"auto", "manual"} else "auto"
        self._current_motion_preference = current_motion_preference if current_motion_preference in {"system", "reduced", "full"} else "system"
        self._theme_labels: list[tuple[QLabel, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing["legacy_24"], TOKENS.spacing["legacy_18"], TOKENS.spacing["legacy_24"], TOKENS.spacing["legacy_18"])
        layout.setSpacing(TOKENS.spacing["legacy_6"])

        def _lbl(txt, size=TOKENS.font_sizes["legacy_9"], bold=False, color=None, align=Qt.AlignmentFlag.AlignCenter,
                 color_role="PRI"):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont(TECH_FONT, size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            resolved = color if color is not None else getattr(C, color_role)
            w.setStyleSheet(f"color: {resolved}; background: transparent;")
            self._theme_labels.append((w, color_role))
            return w

        settings_title = _lbl("◈  Configurações", TOKENS.font_sizes["legacy_13"], True)
        settings_title_font = QFont(UI_FONT, TOKENS.font_sizes["legacy_13"], QFont.Weight.DemiBold)
        settings_title_font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing, TOKENS.letter_spacing['tight']
        )
        settings_title.setFont(settings_title_font)
        layout.addWidget(settings_title)
        layout.addSpacing(TOKENS.spacing["legacy_2"])

        # Tab bar
        tab_bar = QWidget()
        tab_bar.setMinimumHeight(48)
        tb_lay = QHBoxLayout(tab_bar)
        tb_lay.setContentsMargins(TOKENS.spacing["legacy_0"], TOKENS.spacing["legacy_0"], TOKENS.spacing["legacy_0"], TOKENS.spacing["legacy_0"])
        tb_lay.setSpacing(TOKENS.spacing["legacy_4"])

        self._s_tabs: list[QPushButton] = []
        self._s_tab_names = ["Identidade", "Voz", "Tema", "Gráficos"]
        self._s_active_tab = 0

        for i, name in enumerate(self._s_tab_names):
            btn = QPushButton(name)
            btn.setMinimumHeight(40)
            btn.setAccessibleName(f"Configurações: {name.lower()}")
            btn.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_8"], QFont.Weight.Medium))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._switch_s_tab(idx))
            self._s_tabs.append(btn)
            tb_lay.addWidget(btn)

        layout.addWidget(tab_bar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};")
        layout.addWidget(sep)

        # Stacked pages
        from PyQt6.QtWidgets import QStackedWidget
        self._s_stack = QStackedWidget()
        self._s_stack.setStyleSheet("background: transparent;")
        layout.addWidget(self._s_stack, stretch=1)

        # Page 0: Identity
        id_page = QWidget()
        id_page.setStyleSheet("background: transparent;")
        id_lay = QVBoxLayout(id_page)
        id_lay.setContentsMargins(TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_8"], TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_4"])
        id_lay.setSpacing(TOKENS.spacing["legacy_8"])

        id_lay.addWidget(_lbl("◈  Seu nome", TOKENS.font_sizes["legacy_9"], bold=True, color_role="PRI",
                              align=Qt.AlignmentFlag.AlignLeft))
        self._s_name_input = QLineEdit()
        self._s_name_input.setAccessibleName("Seu nome")
        self._s_name_input.setText(current_name)
        self._s_name_input.setPlaceholderText("Por exemplo, Tony")
        self._s_name_input.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_10"]))
        self._s_name_input.setMinimumHeight(44)
        self._s_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.DARK}; color: {C.WHITE};
                border: 1px solid {C.BORDER_B}; border-radius: {TOKENS.radii['legacy_4']}px;
                padding: {TOKENS.spacing['legacy_4']}px {TOKENS.spacing['legacy_10']}px {TOKENS.spacing['legacy_4']}px {TOKENS.spacing['legacy_28']}px;
            }}
            QLineEdit:focus {{
                border: 2px solid {C.PRI};
                background: {C.DARK};
            }}
        """)
        id_lay.addWidget(self._s_name_input)

        save_name = QPushButton("Atualizar identidade")
        save_name.setAccessibleName("Atualizar identidade")
        save_name.setMinimumHeight(44)
        save_name.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_9"], QFont.Weight.Medium))
        save_name.setCursor(Qt.CursorShape.PointingHandCursor)
        save_name.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI_GHO}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: {TOKENS.radii['legacy_4']}px;
                letter-spacing: {TOKENS.letter_spacing['subtle']}px;
            }}
            QPushButton:hover {{
                background: {qss_rgba(C.PRI, 34)};
                border: 1px solid {C.PRI};
                color: {C.ENERGY};
            }}
            QPushButton:focus {{ border: 2px solid {C.PRI}; }}
        """)
        save_name.clicked.connect(lambda: self.name_changed.emit(
            self._s_name_input.text().strip()))
        id_lay.addWidget(save_name)
        self._s_replay_intro = QCheckBox("Reproduzir saudação ao iniciar")
        self._s_replay_intro.setAccessibleName("Reproduzir saudação ao iniciar")
        self._s_replay_intro.setMinimumHeight(40)
        self._s_replay_intro.setChecked(bool(replay_intro))
        self._s_replay_intro.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._s_replay_intro.toggled.connect(self.intro_replay_changed.emit)
        id_lay.addWidget(self._s_replay_intro)
        self._s_replay_tour = QPushButton("Reproduzir visita guiada da interface")
        self._s_replay_tour.setAccessibleName("Reproduzir visita guiada da interface")
        self._s_replay_tour.setMinimumHeight(44)
        self._s_replay_tour.setStyleSheet(f"""
            QPushButton {{ background: {C.DARK}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['sm']}px;
                padding: {TOKENS.spacing['legacy_0']}px {TOKENS.spacing['sm']}px; }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}
            QPushButton:focus {{ border: 2px solid {C.PRI}; }}
        """)
        self._s_replay_tour.clicked.connect(self.tour_replay_requested.emit)
        id_lay.addWidget(self._s_replay_tour)
        id_lay.addStretch()

        self._s_stack.addWidget(id_page)

        # Page 1: speech output and microphone turn-taking preferences.
        voice_page = QWidget()
        voice_page.setStyleSheet("background: transparent;")
        voice_lay = QVBoxLayout(voice_page)
        voice_lay.setContentsMargins(TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_8"], TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_4"])
        voice_lay.setSpacing(TOKENS.spacing["legacy_8"])

        voice_lay.addWidget(_lbl(
            "Voz do ARGUS", TOKENS.font_sizes["legacy_9"], bold=True,
            align=Qt.AlignmentFlag.AlignLeft,
        ))
        self._voice_select_button = QPushButton(
            f"Trocar voz · {VOICE_VALUE_TO_LABEL.get(str(current_voice).lower(), str(current_voice).title())}"
        )
        self._voice_select_button.setAccessibleName("Trocar voz do ARGUS")
        self._voice_select_button.setMinimumHeight(42)
        self._voice_select_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_select_button.clicked.connect(self.voice_selector_requested.emit)
        voice_lay.addWidget(self._voice_select_button)

        voice_lay.addWidget(_lbl(
            "Estilo das respostas faladas", TOKENS.font_sizes["legacy_8"], color_role="TEXT_DIM",
            align=Qt.AlignmentFlag.AlignLeft,
        ))
        self._response_style_combo = QComboBox()
        self._response_style_combo.setAccessibleName("Estilo das respostas faladas")
        self._response_style_combo.setMinimumHeight(42)
        for label, value in (
            ("Mais concisas", "concise"),
            ("Equilibradas", "balanced"),
            ("Mais detalhadas", "detailed"),
        ):
            self._response_style_combo.addItem(label, value)
        style_index = self._response_style_combo.findData(normalize_response_style(current_response_style))
        self._response_style_combo.setCurrentIndex(max(0, style_index))
        self._response_style_combo.currentIndexChanged.connect(self._emit_voice_preferences)
        voice_lay.addWidget(self._response_style_combo)

        voice_lay.addWidget(_lbl(
            "Pausa para entender quando você terminou de falar",
            TOKENS.font_sizes["legacy_8"], color_role="TEXT_DIM",
            align=Qt.AlignmentFlag.AlignLeft,
        ))
        self._vad_silence_slider = QSlider(Qt.Orientation.Horizontal)
        self._vad_silence_slider.setAccessibleName("Pausa para detectar fim da fala")
        self._vad_silence_slider.setRange(MIN_VAD_SILENCE_MS, MAX_VAD_SILENCE_MS)
        self._vad_silence_slider.setSingleStep(50)
        self._vad_silence_slider.setPageStep(100)
        self._vad_silence_slider.setTickInterval(100)
        self._vad_silence_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._vad_silence_slider.setValue(normalize_silence_ms(current_vad_silence_ms))
        voice_lay.addWidget(self._vad_silence_slider)
        self._vad_silence_label = QLabel("")
        self._vad_silence_label.setAccessibleName("Pausa selecionada")
        self._vad_silence_label.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        voice_lay.addWidget(self._vad_silence_label)
        self._vad_silence_note = _lbl(
            "Uma pausa maior evita interromper frases; também pode aumentar um pouco o tempo de resposta.",
            TOKENS.font_sizes["legacy_7"], color_role="TEXT_DIM", align=Qt.AlignmentFlag.AlignLeft,
        )
        self._vad_silence_note.setWordWrap(True)
        voice_lay.addWidget(self._vad_silence_note)
        self._voice_silence_timer = QTimer(self)
        self._voice_silence_timer.setSingleShot(True)
        self._voice_silence_timer.setInterval(400)
        self._voice_silence_timer.timeout.connect(self._emit_voice_preferences)
        self._vad_silence_slider.valueChanged.connect(self._update_vad_silence_label)
        self._vad_silence_slider.valueChanged.connect(lambda _value: self._voice_silence_timer.start())
        self._vad_silence_slider.sliderReleased.connect(self._apply_vad_silence_now)
        self._update_vad_silence_label(self._vad_silence_slider.value())
        voice_lay.addStretch()
        self._s_stack.addWidget(voice_page)

        # Page 2: Theme
        th_page = QWidget()
        th_page.setStyleSheet("background: transparent;")
        th_lay = QVBoxLayout(th_page)
        th_lay.setContentsMargins(TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_8"], TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_4"])
        th_lay.setSpacing(TOKENS.spacing["legacy_6"])

        th_lay.addWidget(_lbl("Tema de cores", TOKENS.font_sizes["legacy_8"], color_role="TEXT_DIM",
                              align=Qt.AlignmentFlag.AlignLeft))

        self._theme_btns: dict[str, QPushButton] = {}
        for key in ThemeManager.theme_names():
            display = {
                "arc_reactor": "Reator Arc",
                "stealth_red": "Vermelho furtivo",
                "vibranium_purple": "Vibranium roxo",
                "nanotech_gold": "Ouro nanotecnológico",
                "platinum": "Platina",
            }.get(key, ThemeManager.theme_display_name(key))
            btn = QPushButton(f"  {display}")
            btn.setAccessibleName(f"Tema {display}")
            btn.setMinimumHeight(44)
            btn.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_9"], QFont.Weight.Medium))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._select_theme(k))
            self._theme_btns[key] = btn
            th_lay.addWidget(btn)

        th_lay.addStretch()
        self._s_stack.addWidget(th_page)

        # Page 3: Graphics, including the device-based automatic profile.
        gfx_page = QWidget()
        gfx_page.setStyleSheet("background: transparent;")
        gfx_lay = QVBoxLayout(gfx_page)
        gfx_lay.setContentsMargins(TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_8"], TOKENS.spacing["legacy_4"], TOKENS.spacing["legacy_4"])
        gfx_lay.setSpacing(TOKENS.spacing["legacy_10"])
        gfx_lay.addWidget(_lbl(
            "Qualidade gráfica", TOKENS.font_sizes["legacy_8"], bold=True, color_role="WHITE_DIM",
            align=Qt.AlignmentFlag.AlignLeft,
        ))
        gfx_lay.addWidget(_lbl(
            "Os perfis preservam suas preferências e entram em vigor na hora.",
            TOKENS.font_sizes["legacy_8"], color_role="WHITE_DIM", align=Qt.AlignmentFlag.AlignLeft,
        ))

        gfx_row = QHBoxLayout()
        gfx_row.setSpacing(TOKENS.spacing["legacy_8"])
        self._graphics_btns: dict[str, GraphicsQualityCard] = {}
        for quality in ("auto", "low", "medium", "high"):
            button = GraphicsQualityCard(quality)
            button.clicked.connect(lambda _, q=quality: self._select_graphics(q))
            self._graphics_btns[quality] = button
            gfx_row.addWidget(button, stretch=1)
        gfx_lay.addLayout(gfx_row)

        self._graphics_note = QLabel("")
        self._graphics_note.setFont(QFont(UI_FONT, TOKENS.font_sizes["legacy_8"]))
        self._graphics_note.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        gfx_lay.addWidget(self._graphics_note)
        motion_row = QHBoxLayout()
        motion_label = QLabel("Movimento")
        motion_label.setAccessibleName("Preferência de movimento")
        motion_label.setStyleSheet(f"color: {C.WHITE_DIM}; background: transparent;")
        motion_row.addWidget(motion_label)
        motion_row.addStretch()
        self._motion_combo = QComboBox()
        self._motion_combo.setAccessibleName("Redução de movimento")
        self._motion_combo.setMinimumSize(180, 44)
        for label, value in (("Usar sistema", "system"), ("Reduzido", "reduced"), ("Completo", "full")):
            self._motion_combo.addItem(label, value)
        index = self._motion_combo.findData(self._current_motion_preference)
        self._motion_combo.setCurrentIndex(max(0, index))
        self._motion_combo.currentIndexChanged.connect(
            lambda _: self._set_motion_preference(self._motion_combo.currentData())
        )
        motion_row.addWidget(self._motion_combo)
        gfx_lay.addLayout(motion_row)
        self._motion_note = QLabel("Baixa qualidade gráfica sempre desativa o movimento contínuo.")
        self._motion_note.setAccessibleName("Comportamento do movimento em baixa qualidade")
        self._motion_note.setWordWrap(True)
        gfx_lay.addWidget(self._motion_note)
        gfx_lay.addStretch()
        self._s_stack.addWidget(gfx_page)

        self._switch_s_tab(0)
        self._highlight_theme(current_theme)
        self._highlight_graphics(
            "auto" if self._current_graphics_mode == "auto" else self._current_graphics
        )
        self._setup_overlay_base(close_callback=self.hide)
        self.refresh_theme()

    def _update_vad_silence_label(self, value: int):
        seconds = f"{int(value) / 1000:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        self._vad_silence_label.setText(f"{seconds} s")

    def _emit_voice_preferences(self, *_):
        style = self._response_style_combo.currentData()
        self.voice_preferences_changed.emit(
            normalize_response_style(style), self._vad_silence_slider.value()
        )

    def _apply_vad_silence_now(self):
        self._voice_silence_timer.stop()
        self._emit_voice_preferences()

    def _switch_s_tab(self, idx: int):
        self._s_active_tab = idx
        self._s_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._s_tabs):
            if i == idx:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI_GHO}; color: {C.PRI};
                        border: 2px solid {C.PRI}; border-bottom: 2px solid {C.PRI};
                        border-radius: {TOKENS.radii['legacy_3']}px; padding: {TOKENS.spacing['legacy_0']}px {TOKENS.spacing['legacy_8']}px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {C.WHITE_DIM};
                        border: 1px solid {qss_rgba(C.BORDER, 68)}; border-radius: {TOKENS.radii['legacy_3']}px; padding: {TOKENS.spacing['legacy_0']}px {TOKENS.spacing['legacy_8']}px;
                    }}
                    QPushButton:hover {{ color: {C.PRI}; background: {C.PRI_GHO};
                                         border: 1px solid {C.BORDER_B}; }}
                    QPushButton:focus {{ color: {C.WHITE}; border: 2px solid {C.PRI}; }}
                """)

    def _select_theme(self, key: str):
        self._current_theme = key
        self.theme_changed.emit(key)
        self._highlight_theme(key)

    def _select_graphics(self, quality: str):
        if quality == "auto":
            self._current_graphics_mode = "auto"
            self._highlight_graphics("auto")
            self.graphics_mode_changed.emit("auto")
            return
        value = _normalize_graphics_quality(quality)
        self._current_graphics = value
        self._current_graphics_mode = "manual"
        self._highlight_graphics(value)
        label = {"low": "baixa", "medium": "média", "high": "alta"}[value]
        self._graphics_note.setText(f"Qualidade {label} ativa.")
        self.graphics_mode_changed.emit("manual")
        self.graphics_changed.emit(value)

    def _set_motion_preference(self, preference: str):
        value = str(preference or "system")
        if value not in {"system", "reduced", "full"}:
            value = "system"
        self._current_motion_preference = value
        self.motion_preference_changed.emit(value)

    def _highlight_graphics(self, quality: str):
        value = quality if quality == "auto" else _normalize_graphics_quality(quality)
        for key, button in self._graphics_btns.items():
            button.refresh_theme(key == value)

    def set_auto_graphics_result(self, quality: str, reason: str):
        value = _normalize_graphics_quality(quality)
        label = {"low": "Baixa", "medium": "Média", "high": "Alta"}[value]
        self._graphics_btns["auto"]._desc.setText(f"{label} · recomendada")
        self._graphics_note.setText(str(reason))
        if self._current_graphics_mode == "auto":
            self._highlight_graphics("auto")

    def refresh_theme(self):
        self.setStyleSheet(f"""
            SettingsOverlay {{
                background: {C.BG}; border: 1px solid {C.BORDER_B}; border-radius: {TOKENS.radii['legacy_8']}px;
            }}
        """)
        for label, color_role in self._theme_labels:
            label.setStyleSheet(
                f"color: {getattr(C, color_role, C.TEXT)}; background: transparent;"
            )
        self._s_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.DARK}; color: {C.WHITE};
                border: 1px solid {C.BORDER_B}; border-radius: {TOKENS.radii['legacy_4']}px;
                padding: {TOKENS.spacing['legacy_4']}px {TOKENS.spacing['legacy_10']}px {TOKENS.spacing['legacy_4']}px {TOKENS.spacing['legacy_28']}px;
            }}
            QLineEdit:focus {{ border: 2px solid {C.PRI}; background: {C.DARK}; }}
        """)
        self._switch_s_tab(self._s_active_tab)
        self._highlight_theme(self._current_theme)
        self._highlight_graphics(
            "auto" if self._current_graphics_mode == "auto" else self._current_graphics
        )
        self._graphics_note.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._motion_combo.setStyleSheet(f"""
            QComboBox {{ background: {C.DARK}; color: {C.WHITE}; border: 1px solid {C.BORDER};
                border-radius: {TOKENS.radii['sm']}px;
                padding: {TOKENS.spacing['legacy_0']}px {TOKENS.spacing['sm']}px; }}
            QComboBox:focus {{ border: 2px solid {C.PRI}; }}
            QComboBox QAbstractItemView {{ background: {C.PANEL}; color: {C.WHITE};
                selection-background-color: {C.PRI_GHO}; selection-color: {C.PRI}; }}
        """)
        self._motion_note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._s_replay_tour.setStyleSheet(f"""
            QPushButton {{ background: {C.DARK}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['sm']}px;
                padding: {TOKENS.spacing['legacy_0']}px {TOKENS.spacing['sm']}px; }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}
            QPushButton:focus {{ border: 2px solid {C.PRI}; }}
        """)

    def _highlight_theme(self, key: str):
        for k, btn in self._theme_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI}; color: {C.BG};
                        border: none; border-radius: {TOKENS.radii['legacy_4']}px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.DARK}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER}; border-radius: {TOKENS.radii['legacy_4']}px;
                    }}
            QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.BORDER_B}; }}
            QPushButton:focus {{ border: 2px solid {C.PRI}; }}
            QPushButton:focus {{ border: 2px solid {C.PRI}; }}
                """)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        super().keyPressEvent(event)

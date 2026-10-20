from __future__ import annotations

import json
import hashlib
import math
import os
import platform
import random
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QMimeData, QObject, QPointF, QPropertyAnimation,
    QRect, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal,
)

from PyQt6.QtGui import (
    QAction, QBrush, QColor, QDragEnterEvent, QDropEvent, QFont as _QFont,
    QFontDatabase, QIcon, QImage, QKeySequence, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QShortcut, QDesktopServices,
)

from .first_run import (
    INTRO_MASTERING_VERSION,
    INTRO_PERFORMANCE_VERSION, INTRO_SAMPLE_RATE, INTRO_SEQUENCE_VERSION,
    INTRO_VOICE_CACHE_DIR, FirstRunIntroOverlay, IntroChapter,
    _configure_intro_tts_renderers,
    _cache_intro_voice_async, _daily_greeting,
    _generate_intro_aligned_speech_pcm, _generate_intro_segmented_speech_pcm,
    _generate_intro_speech_pcm, _intro_caption_boundaries, _intro_voice_cache_path,
    _is_intro_quota_error, _load_intro_timing_cache, _master_intro_pcm,
    _pcm_duration_seconds, _play_intro_pcm, _prepare_intro_voice_cache,
    _render_intro_segments_with_live, _render_intro_with_live,
    _tour_captions, _tour_chapters, _tour_narration, _voice_display_name,
    _write_intro_timing_cache,
)
from core.api_key_validator import ApiKeyValidationResult
from core.voice_catalog import (
    DEFAULT_PROVIDER, DEFAULT_VOICE_ID, EXTERNAL_PROVIDERS,
    PROVIDER_TUTORIAL, PROVIDER_VOICES,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QCheckBox, QFormLayout, QFrame, QGraphicsOpacityEffect,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QSystemTrayIcon, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # This module lives in the ui/ package, but assets and local config live
    # beside main.py at the project root.
    return Path(__file__).resolve().parent.parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
FONT_DIR   = BASE_DIR / "assets" / "fonts"
UI_SETTINGS_FILE = Path.home() / ".argus" / "config" / "settings.json"
LAYOUT_SETTINGS_FILE = Path.home() / ".argus" / "config" / "layout_settings.json"

# Each profile changes both cadence and rendering density.  Keeping this data
# centralized makes the Settings UI, the renderer, and ARGUS voice commands
# agree on what Low / Medium / High actually mean.
GRAPHICS_PROFILES = {
    "low": {
        "frame_ms": 50,       # 20 FPS target
        "render_stride": 3,
        "wave_stride": 3,
        "noise_count": 0,
        "scanline_step": 8,
        "antialias": False,
        "activity_nodes": 10,
        "metrics_ms": 3500,
    },
    "medium": {
        "frame_ms": 33,       # 30 FPS target
        "render_stride": 2,
        "wave_stride": 2,
        "noise_count": 60,
        "scanline_step": 6,
        "antialias": True,
        "activity_nodes": 16,
        "metrics_ms": 2000,
    },
    "high": {
        "frame_ms": 16,       # 60 FPS target
        "render_stride": 1,
        "wave_stride": 1,
        "noise_count": 200,
        "scanline_step": 4,
        "antialias": True,
        "activity_nodes": 24,
        "metrics_ms": 1200,
    },
}

def _normalize_graphics_quality(quality: str | None) -> str:
    value = str(quality or "medium").strip().lower()
    aliases = {
        "med": "medium", "mid": "medium", "normal": "medium",
        "balanced": "medium", "performance": "low", "battery": "low",
        "max": "high", "maximum": "high", "ultra": "high",
    }
    value = aliases.get(value, value)
    if value not in GRAPHICS_PROFILES:
        raise ValueError("Graphics quality must be low, medium, or high.")
    return value

def _read_ui_settings() -> dict:
    try:
        if UI_SETTINGS_FILE.exists():
            data = json.loads(UI_SETTINGS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def get_graphics_quality() -> str:
    try:
        return _normalize_graphics_quality(_read_ui_settings().get("graphics_quality", "medium"))
    except ValueError:
        return "medium"

def set_graphics_quality(quality: str) -> str:
    value = _normalize_graphics_quality(quality)
    settings = _read_ui_settings()
    settings["graphics_quality"] = value
    settings["graphics_quality_mode"] = "manual"
    UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return value

def _graphics_mode_from_settings(settings: dict) -> str:
    saved_mode = str(settings.get("graphics_quality_mode", "")).strip().lower()
    if saved_mode in {"auto", "manual"}:
        return saved_mode
    # Older releases stored a selected profile but had no auto mode. Preserve
    # that choice; only settings without any profile should use detection.
    return "manual" if "graphics_quality" in settings else "auto"

def get_graphics_mode() -> str:
    return _graphics_mode_from_settings(_read_ui_settings())

def save_auto_graphics_result(report: dict) -> str:
    """Save a device-based profile only while the user still has auto enabled."""
    quality = _normalize_graphics_quality(report.get("quality", "medium"))
    settings = _read_ui_settings()
    if _graphics_mode_from_settings(settings) == "manual":
        if "graphics_quality_mode" not in settings:
            settings["graphics_quality_mode"] = "manual"
            UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return _normalize_graphics_quality(settings.get("graphics_quality", "medium"))
    settings["graphics_quality_mode"] = "auto"
    settings["graphics_quality"] = quality
    settings["graphics_auto_fingerprint"] = str(report.get("fingerprint", ""))
    settings["graphics_auto_report"] = dict(report)
    UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return quality

def qss_rgba(color: str, alpha: int) -> str:
    parsed = QColor(color)
    return f"rgba({parsed.red()}, {parsed.green()}, {parsed.blue()}, {max(0, min(255, int(alpha)))})"

def _load_intro_settings() -> tuple[bool, bool]:
    data = _read_ui_settings()
    version = int(data.get("intro_version", 0) or 0)
    completed = bool(data.get("intro_completed", False)) and version >= INTRO_SEQUENCE_VERSION
    # Fresh installs go straight to the console after the one-time tour. Honor
    # an explicit legacy replay preference while migrating its default to off.
    greeting = bool(data.get("startup_greeting_enabled", data.get("intro_every_launch", False)))
    return completed, greeting

def _save_intro_settings(completed: bool, greeting_enabled: bool) -> None:
    data = _read_ui_settings()
    data.pop("intro_every_launch", None)
    data["intro_completed"] = bool(completed)
    data["startup_greeting_enabled"] = bool(greeting_enabled)
    data["intro_version"] = INTRO_SEQUENCE_VERSION
    UI_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def route_argus_ui_command(command: str):
    normalized = " ".join(re.sub(r"[^a-z ]+", " ", str(command or "").lower()).split())
    patterns = (
        r"^(?:argus )?(?:quit|exit|close)(?: argus)?$",
        r"^shut yourself down$",
        r"^(?:argus )?turn yourself off$",
        r"^go offline(?: argus)?$",
    )
    return ("quit_argus", None) if any(re.fullmatch(pattern, normalized) for pattern in patterns) else None
VOICE_OPTIONS = list(PROVIDER_VOICES["gemini"])
VOICE_VALUE_TO_LABEL = {value: label for label, value in VOICE_OPTIONS}
VOICE_LABEL_TO_VALUE = {label.lower(): value for label, value in VOICE_OPTIONS}

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"
from .theme import C, DISPLAY_FONT, QFont, TECH_FONT, ThemeManager, TOKENS, UI_FONT, _load_bundled_fonts, qcol
_DEFAULT_W = TOKENS.layout_sizes["desktop_width"]
_DEFAULT_H = TOKENS.layout_sizes["desktop_height"]
_MIN_W = TOKENS.layout_sizes["desktop_min_width"]
_MIN_H = TOKENS.layout_sizes["desktop_min_height"]
_NAV_W = TOKENS.layout_sizes["navigation_rail"]
_LEFT_W = TOKENS.layout_sizes["transcript_panel"]
_RIGHT_W = TOKENS.layout_sizes["execution_panel"]

# ---------------------------------------------------------------------------
# ChatBubbleWidget — chat-style conversation view
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# FocusDialogueWidget — cinematic lower-third for the focused interface
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ResearchProgressWidget — compact background deep-research status
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ToastNotification — floating notification system
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ToolProgressWidget — active tool execution indicator
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CompactModeWidget — floating mini arc reactor
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Popup System - Contextual holographic popups orbiting the AI Core
# ---------------------------------------------------------------------------

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

# Popup configurations

# Configuration classes for customizable UI elements

# ---------------------------------------------------------------------------
# AgentGridWidget — live autonomous agent status panel
# ---------------------------------------------------------------------------

            # line_lbl hidden — no connector

# ---------------------------------------------------------------------------
# ToolLogWidget — shows tool execution history with status
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MissionControlPanel — tabbed right panel
# ---------------------------------------------------------------------------

_FILE_ICONS = {
    "image":   ("🖼", TOKENS.file_category_colors["image"]),
    "video":   ("🎬", TOKENS.file_category_colors["video"]),
    "audio":   ("🎵", TOKENS.file_category_colors["audio"]),
    "pdf":     ("📄", TOKENS.file_category_colors["pdf"]),
    "word":    ("📝", TOKENS.file_category_colors["word"]),
    "excel":   ("📊", TOKENS.file_category_colors["excel"]),
    "code":    ("💻", TOKENS.file_category_colors["code"]),
    "archive": ("📦", TOKENS.file_category_colors["archive"]),
    "pptx":    ("📊", TOKENS.file_category_colors["pptx"]),
    "text":    ("📃", TOKENS.file_category_colors["text"]),
    "data":    ("🔧", TOKENS.file_category_colors["data"]),
    "unknown": ("📎", TOKENS.file_category_colors["unknown"]),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

# ---------------------------------------------------------------------------
# Shared mixin: draggable + X-close button for all overlay widgets
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ShortcutsOverlay — keyboard shortcuts help panel
# ---------------------------------------------------------------------------

from .overlays.base import _OverlayBase

# ---------------------------------------------------------------------------
# SettingsOverlay — unified settings panel with tabs
# ---------------------------------------------------------------------------

def _minimize_or_restore(win: QMainWindow):
    """Minimize or restore the window.

    Requirement: first press minimizes; second press restores.
    """
    if win.isMinimized():
        win.showNormal()
        win.raise_()
        win.activateWindow()
        return

    win.showMinimized()

from core.secret_store import get_secret_store

from .conversation import ChatBubbleWidget, FocusDialogueWidget, _SubtitleWidget

from .notifications import BasePopup, PopupConfig, PopupManager, POPUP_CONFIGS, PopupPriority, PopupType, PresenceSystem, ToastManager, ToastNotification
from .compact import CompactModeWidget
from .files import FileDropZone, _DropCanvas, _file_category, _fmt_size
from .console import LogWidget
from .overlays.setup import SetupOverlay
from .overlays.settings import GraphicsQualityCard, SettingsOverlay, ShortcutsOverlay
from .overlays.identity import KeyTutorialOverlay, NameSignInOverlay, VoiceSelectOverlay, VoiceSelectorOverlay
VoicePresetOverlay = VoiceSelectorOverlay
TTSProviderOverlay = VoiceSelectorOverlay
from .tools import MissionControlPanel, ResearchProgressWidget, TaskQueueWidget, ToolLogWidget, ToolProgressWidget
from .hud import AIActivityCanvas, AIActivityConfig, AgentGridWidget, HudCanvas, HudConfig, MetricBar, SparklineBar, _SysMetrics, _get_metrics
from .vision import VisionPreviewWindow
from .windows import (
    _MainWindowCommandMixin, _MainWindowIdentityMixin,
    _MainWindowInteractionMixin, _MainWindowLayoutMixin,
    _MainWindowOnboardingMixin, _MainWindowSettingsMixin,
    _MainWindowStartupMixin, _MainWindowStyleMixin,
)

class MainWindow(_MainWindowStartupMixin, _MainWindowSettingsMixin, _MainWindowCommandMixin, _MainWindowStyleMixin, _MainWindowLayoutMixin, _MainWindowInteractionMixin, _MainWindowOnboardingMixin, _MainWindowIdentityMixin, QMainWindow):


    _log_sig       = pyqtSignal(str)


    _state_sig     = pyqtSignal(str)


    _voice_sig     = pyqtSignal(str)


    _sub_sig       = pyqtSignal(str)


    _sub_clear_sig = pyqtSignal()


    _sub_hold_sig  = pyqtSignal()


    _mode_sig      = pyqtSignal(str)          # context mode for AIActivityCanvas


    _task_sig      = pyqtSignal(str, str)     # (task_name, status) for TaskQueueWidget


    _tool_sig      = pyqtSignal(str)          # tool log line for ToolLogWidget


    _theme_sig     = pyqtSignal(str)


    _graphics_sig  = pyqtSignal(str)


    _vision_preview_sig = pyqtSignal(str)


    _vision_preview_hide_sig = pyqtSignal(int)


    _research_progress_sig = pyqtSignal(object)


    _research_progress_finish_sig = pyqtSignal(str, str)


    _research_progress_hide_sig = pyqtSignal()


    _presentation_progress_sig = pyqtSignal(object)


    _presentation_progress_finish_sig = pyqtSignal(str, str)


    _presentation_progress_hide_sig = pyqtSignal()


    _ui_command_sig = pyqtSignal(str)


    _intro_prepared_sig = pyqtSignal(bool, str)

from .facade import ArgusUI, _RootShim

def _sync_ui_component_globals():
    """Keep split component modules compatible with the legacy patch surface."""
    for module_name, module in tuple(sys.modules.items()):
        if not module_name.startswith("ui.") or module is sys.modules.get(__name__):
            continue
        namespace = getattr(module, "__dict__", None)
        if namespace is None:
            continue
        for name, value in globals().items():
            namespace.setdefault(name, value)

_sync_ui_component_globals()

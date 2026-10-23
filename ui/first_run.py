"""First-run introduction, narration, and audio-cache helpers for the desktop UI."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import struct
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget


INTRO_SEQUENCE_VERSION = 5
INTRO_PERFORMANCE_VERSION = "pcm-v1"
INTRO_MASTERING_VERSION = "peak-safe-v1"
INTRO_SAMPLE_RATE = 24_000
INTRO_VOICE_CACHE_DIR = Path.home() / ".argus" / "cache" / "intro"

_intro_tts_renderer: Callable | None = None
_intro_tts_segmented_renderer: Callable | None = None


def _configure_intro_tts_renderers(
    renderer: Callable | None,
    segmented_renderer: Callable | None,
) -> None:
    """Inject app-owned voice services without coupling UI modules to an SDK."""
    global _intro_tts_renderer, _intro_tts_segmented_renderer
    _intro_tts_renderer = renderer
    _intro_tts_segmented_renderer = segmented_renderer

_GREETING_CAPTIONS = (
    "ARGUS está online.",
    "Seus pedidos por voz e texto fazem parte da mesma conversa.",
)


@dataclass(frozen=True)
class IntroChapter:
    focus: str
    label: str
    tab_index: int
    caption: str


def _ui_symbol(name: str, default=None):
    """Resolve exported ui.py values at call time so tests and themes stay patchable."""
    module = sys.modules.get("ui")
    if module is not None and hasattr(module, name):
        return getattr(module, name)
    return globals().get(name, default)


def _daily_greeting(now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    if 5 <= hour < 12:
        return "Bom dia. Eu sou ARGUS."
    if 12 <= hour < 18:
        return "Boa tarde. Eu sou ARGUS."
    return "Boa noite. Eu sou ARGUS."


def _tour_chapters(now: datetime | None = None) -> tuple[IntroChapter, ...]:
    greeting = _daily_greeting(now)
    copy = (
        ("core", "REATOR", -1, f"{greeting} Seu assistente pessoal ajuda você a trabalhar com clareza e foco."),
        ("subtitles", "LEGENDAS", -1, "Falas e legendas aparecem juntas para acompanhar cada resposta enquanto ARGUS escuta."),
        ("header", "ESTADO", -1, "O cabeçalho mostra conexão e controles disponíveis, sem sugerir medições que não existem."),
        ("awareness", "CONSCIÊNCIA", -1, "Consciência resume informações disponíveis nesta sessão, sem criar diagnósticos ou telemetria fictícia."),
        ("mission_comms", "COMUNICAÇÃO", 0, "Comunicações mantém a conversa visível. Voz e texto seguem o mesmo fluxo, com digitação pronta."),
        ("mission_tasks", "TAREFAS", 1, "Tarefas mostra o trabalho em andamento e explica o painel vazio até a primeira atividade real."),
        ("mission_assets", "ARQUIVOS", 2, "Arquivos reúne itens anexados à conversa; o painel fica claro quando ainda não há arquivos."),
        ("mission_tools", "FERRAMENTAS", 3, "Ferramentas registra ações reais e seus resultados. Cada linha corresponde a uma solicitação executada."),
        ("input", "MENSAGEM", 0, "Para escrever, use o campo de mensagem; pressione Enter para enviar ou fale com o microfone ativo."),
        ("core", "REATOR", -1, "O reator central reflete meu estado atual; seus movimentos respondem à atividade, sem fingir medições ocultas."),
        ("dock", "COMANDOS", 0, "A barra de comandos permite silenciar o microfone, trocar voz, ajustar aparência, abrir configurações ou sair."),
        ("header", "PREFERÊNCIAS", -1, "Qualidade gráfica menor ajuda em computadores modestos. Movimento reduzido respeita sua preferência e evita animações desnecessárias."),
        ("subtitles", "TRANSPARÊNCIA", -1, "Se uma resposta não estiver disponível, ARGUS informa com clareza. Latência e níveis inexistentes não são inventados."),
        ("handoff", "PRONTO", -1, "Pronto para começar: peça uma pesquisa, lembrete, tarefa com arquivos ou ação no computador usando palavras simples."),
    )
    return tuple(IntroChapter(*chapter) for chapter in copy)


def _tour_captions(now: datetime | None = None) -> tuple[str, ...]:
    return tuple(chapter.caption for chapter in _tour_chapters(now))


def _tour_narration(now: datetime | None = None) -> str:
    return " ".join(_tour_captions(now))


def _intro_voice_cache_path(
    voice_name: str,
    narration: str,
    sequence_kind: str = "greeting",
) -> Path:
    cache_dir = Path(_ui_symbol("INTRO_VOICE_CACHE_DIR", INTRO_VOICE_CACHE_DIR))
    performance = _ui_symbol("INTRO_PERFORMANCE_VERSION", INTRO_PERFORMANCE_VERSION)
    mastering = _ui_symbol("INTRO_MASTERING_VERSION", INTRO_MASTERING_VERSION)
    sequence_version = _ui_symbol("INTRO_SEQUENCE_VERSION", INTRO_SEQUENCE_VERSION)
    source = "\0".join((
        str(sequence_kind), str(sequence_version), str(voice_name).strip().lower(),
        str(performance), str(mastering), str(narration),
    ))
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.pcm"


def _timing_cache_path(pcm_path: Path) -> Path:
    return pcm_path.with_suffix(pcm_path.suffix + ".timing.json")


def _pcm_duration_seconds(pcm: bytes) -> float:
    sample_rate = int(_ui_symbol("INTRO_SAMPLE_RATE", INTRO_SAMPLE_RATE))
    if sample_rate <= 0:
        return 0.0
    return len(pcm) / 2 / sample_rate


def _load_intro_timing_cache(
    pcm_path: Path,
    caption_count: int,
    duration: float,
) -> list[float] | None:
    try:
        payload = json.loads(_timing_cache_path(pcm_path).read_text(encoding="utf-8"))
        boundaries = [float(value) for value in payload["boundaries"]]
        if len(boundaries) != caption_count + 1 or not boundaries:
            return None
        if abs(boundaries[0]) > 0.02 or abs(boundaries[-1] - duration) > 0.02:
            return None
        if any(right < left for left, right in zip(boundaries, boundaries[1:])):
            return None
        return boundaries
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _write_intro_timing_cache(pcm_path: Path, boundaries: list[float]) -> None:
    target = _timing_cache_path(pcm_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"boundaries": [float(value) for value in boundaries]}, indent=2),
        encoding="utf-8",
    )


def _intro_caption_boundaries(pcm: bytes, captions: tuple[str, ...]) -> list[float]:
    duration = _pcm_duration_seconds(pcm)
    count = len(captions)
    if count <= 0:
        return [0.0, duration]
    if len(pcm) < 2 or duration <= 0:
        return [duration * index / count for index in range(count + 1)]

    sample_rate = int(_ui_symbol("INTRO_SAMPLE_RATE", INTRO_SAMPLE_RATE))
    samples_per_frame = max(1, sample_rate // 100)
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm[:len(pcm) // 2 * 2])
    quiet_runs: list[tuple[float, float]] = []
    run_start = None
    frame_count = (len(samples) + samples_per_frame - 1) // samples_per_frame
    for frame_index in range(frame_count):
        start = frame_index * samples_per_frame
        frame = samples[start:start + samples_per_frame]
        rms = (sum(sample * sample for sample in frame) / max(1, len(frame))) ** 0.5
        quiet = rms < 160
        if quiet and run_start is None:
            run_start = start
        if run_start is not None and (not quiet or frame_index == frame_count - 1):
            end = start if not quiet else len(samples)
            if end - run_start >= int(sample_rate * 0.08):
                quiet_runs.append((run_start / sample_rate, end / sample_rate))
            run_start = None

    boundaries = [0.0]
    for index in range(1, count):
        target = duration * index / count
        candidates = [
            (start + end) / 2
            for start, end in quiet_runs
            if start > boundaries[-1] and end < duration
        ]
        nearest = min(candidates, key=lambda value: abs(value - target), default=None)
        if nearest is not None and abs(nearest - target) <= max(0.55, duration / count * 0.35):
            target = nearest
        target = max(boundaries[-1], min(duration, target))
        boundaries.append(target)
    boundaries.append(duration)
    return boundaries


def _master_intro_pcm(pcm: bytes) -> bytes:
    if len(pcm) % 2:
        pcm = pcm[:-1]
    if not pcm:
        return pcm
    samples = list(struct.unpack(f"<{len(pcm) // 2}h", pcm))
    peak = max(abs(sample) for sample in samples)
    ceiling = 31_000
    if peak <= ceiling or peak == 0:
        return pcm
    scale = ceiling / peak
    mastered = [max(-32768, min(32767, round(sample * scale))) for sample in samples]
    return struct.pack(f"<{len(mastered)}h", *mastered)


def _voice_display_name(voice_name: str) -> str:
    voice_map = _ui_symbol("VOICE_VALUE_TO_LABEL", {})
    return voice_map.get(str(voice_name).strip().lower(), str(voice_name).strip().title())


def _is_intro_quota_error(error: BaseException) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in (
        "429", "resource_exhausted", "quota", "rate limit",
    ))


async def _render_intro_with_live(
    narration: str,
    voice_name: str,
    api_key: str,
) -> bytes:
    renderer = _intro_tts_renderer
    if renderer is None:
        raise RuntimeError("First-run voice rendering is not configured by the application.")
    return await renderer(narration, voice_name, api_key)


async def _render_intro_segments_with_live(
    captions: tuple[str, ...],
    voice_name: str,
    api_key: str,
) -> tuple[bytes, list[int]]:
    renderer = _intro_tts_segmented_renderer
    if renderer is None:
        raise RuntimeError("Segmented first-run voice rendering is not configured by the application.")
    return await renderer(captions, voice_name, api_key)


def _generate_intro_speech_pcm(narration: str, voice_name: str, api_key: str) -> bytes:
    renderer = _ui_symbol("_render_intro_with_live")
    pcm = asyncio.run(renderer(narration, voice_name, api_key))
    return _ui_symbol("_master_intro_pcm")(pcm)


def _generate_intro_segmented_speech_pcm(
    captions: tuple[str, ...],
    voice_name: str,
    api_key: str,
) -> tuple[bytes, list[float]]:
    renderer = _ui_symbol("_render_intro_segments_with_live")
    pcm, byte_boundaries = asyncio.run(renderer(captions, voice_name, api_key))
    mastered = _ui_symbol("_master_intro_pcm")(pcm)
    sample_rate = int(_ui_symbol("INTRO_SAMPLE_RATE", INTRO_SAMPLE_RATE))
    scale = 2 * sample_rate
    return mastered, [boundary / scale for boundary in byte_boundaries]


def _generate_intro_aligned_speech_pcm(
    captions: tuple[str, ...],
    voice_name: str,
    api_key: str,
) -> tuple[bytes, list[float]]:
    narration = " ".join(captions)
    pcm = _ui_symbol("_generate_intro_speech_pcm")(narration, voice_name, api_key)
    boundaries = _ui_symbol("_intro_caption_boundaries")(pcm, captions)
    return pcm, boundaries


def _prepare_intro_voice_cache(
    voice_name: str,
    narration: str,
    api_key: str,
    sequence_kind: str = "greeting",
    attempts: int = 3,
    captions: tuple[str, ...] | None = None,
) -> tuple[bool, str]:
    cache_path = Path(_ui_symbol("_intro_voice_cache_path")(
        voice_name, narration, sequence_kind
    ))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.is_file() and cache_path.stat().st_size > 0:
        if captions:
            duration = _pcm_duration_seconds(cache_path.read_bytes())
            if _ui_symbol("_load_intro_timing_cache")(
                cache_path, len(captions), duration
            ) is None:
                _ui_symbol("_write_intro_timing_cache")(
                    cache_path, _ui_symbol("_intro_caption_boundaries")(
                        cache_path.read_bytes(), captions
                    )
                )
        return True, ""

    last_message = "Gemini TTS returned no audio."
    for attempt in range(max(1, int(attempts))):
        try:
            if captions:
                generator = _ui_symbol("_generate_intro_aligned_speech_pcm")
                pcm, boundaries = generator(captions, voice_name, api_key)
            else:
                generator = _ui_symbol("_generate_intro_speech_pcm")
                pcm = generator(narration, voice_name, api_key)
                boundaries = None
            if not pcm:
                last_message = "Gemini TTS returned no audio."
                continue
            cache_path.write_bytes(pcm)
            if boundaries is not None:
                _ui_symbol("_write_intro_timing_cache")(cache_path, boundaries)
            return True, ""
        except Exception as exc:
            last_message = str(exc)
            if _is_intro_quota_error(exc):
                return False, last_message
            if attempt + 1 < max(1, int(attempts)):
                time.sleep(min(0.25 * (attempt + 1), 1.0))
    return False, last_message


def _cache_intro_voice_async(voice_name: str):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    narration = _tour_narration()
    captions = _tour_captions()
    worker = threading.Thread(
        target=_prepare_intro_voice_cache,
        args=(voice_name, narration, api_key),
        kwargs={"sequence_kind": "tour", "captions": captions},
        daemon=True,
    )
    worker.start()
    return worker


def _play_intro_pcm(
    pcm: bytes,
    progress_callback: Callable[[float], None] | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """Play cached mono 16-bit PCM without falling back to platform TTS voices."""
    if not pcm:
        raise RuntimeError("The introduction audio cache is empty.")
    import sounddevice as sd

    sample_rate = int(_ui_symbol("INTRO_SAMPLE_RATE", INTRO_SAMPLE_RATE))
    chunk_size = max(2, sample_rate // 10 * 2)
    if stop_event is not None and stop_event.is_set():
        return
    stream = sd.RawOutputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    total = len(pcm)
    try:
        stream.start()
        for offset in range(0, total, chunk_size):
            if stop_event is not None and stop_event.is_set():
                break
            chunk = pcm[offset:offset + chunk_size]
            stream.write(chunk)
            if progress_callback is not None:
                progress_callback(min(1.0, (offset + len(chunk)) / total))
    finally:
        stream.stop()
        stream.close()


class FirstRunIntroOverlay(QWidget):
    """Accessible, audio-clocked introduction overlay with optional focus spotlight."""

    finished = pyqtSignal()
    caption_changed = pyqtSignal(str)
    chapter_changed = pyqtSignal(str, str, int)
    _speech_progress = pyqtSignal(float)
    _speech_finished_signal = pyqtSignal(float)
    _speech_error = pyqtSignal(str)

    _TOUR_DURATION_S = 90.0
    _GREETING_DURATION_S = 18.0
    _FINAL_HOLD_S = 1.2
    _CAPTIONS = _GREETING_CAPTIONS

    def __init__(
        self,
        parent=None,
        duration_s: float = _GREETING_DURATION_S,
        speak: bool = False,
        voice_name: str = "charon",
        api_key: str = "",
        chapters: tuple[IntroChapter, ...] | None = None,
        narration: str | None = None,
        captions: tuple[str, ...] | None = None,
        sequence_kind: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("FirstRunIntroOverlay")
        self.setAccessibleName("ARGUS first-run introduction")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._chapters = tuple(chapters or ())
        self._CAPTIONS = tuple(captions or (
            tuple(chapter.caption for chapter in self._chapters)
            if self._chapters else self.__class__._CAPTIONS
        ))
        self._narration = narration or " ".join(self._CAPTIONS)
        self._sequence_kind = sequence_kind or ("tour" if self._chapters else "greeting")
        self._duration_s = max(0.1, float(duration_s))
        self._voice_name = str(voice_name or "charon").strip().lower()
        self._api_key = str(api_key or "")
        self._started_at = time.monotonic()
        self._last_caption_index = -1
        self._finished = False
        self._audio_driven = bool(speak)
        self._audio_duration = 0.0
        self._speech_position = 0.0
        self._speech_finished_at: float | None = None
        self._caption_boundaries: list[float] = []
        self._spotlight_target = QRectF()
        self._spotlight_label = ""
        self._spotlight_shape = "rect"
        self._persistent_cutouts: list[QRectF] = []
        self._reduced_motion = False
        self._speech_stop = threading.Event()
        self._speech_thread: threading.Thread | None = None

        self._skip_button = QPushButton("Pular introdução", self)
        self._skip_button.setAccessibleName("Pular introdução do ARGUS")
        self._skip_button.setMinimumSize(184, 42)
        self._skip_button.setCursor(Qt.CursorShape.PointingHandCursor)
        colors = _ui_symbol("C")
        tokens = _ui_symbol("TOKENS")
        if colors is not None and tokens is not None:
            self._skip_button.setStyleSheet(f"""
                QPushButton {{ background: {colors.BG}; color: {colors.PRI};
                    border: 1px solid {colors.PRI_DIM}; border-radius: {tokens.radii['control']}px; padding: {tokens.spacing['legacy_0']}px {tokens.spacing['legacy_14']}px; }}
                QPushButton:hover {{ background: {colors.PRI_GHO}; border-color: {colors.PRI}; }}
                QPushButton:focus {{ border: 2px solid {colors.PRI}; }}
            """)
        self._skip_button.clicked.connect(self.finish)

        self._speech_progress.connect(self._on_speech_progress)
        self._speech_finished_signal.connect(self._on_speech_finished)
        self._speech_error.connect(self._on_speech_error)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._skip_button.move(
            max(0, (self.width() - self._skip_button.width()) // 2),
            max(0, self.height() - self._skip_button.height() - 24),
        )

    @property
    def _timeline_duration(self) -> float:
        return self._audio_duration if self._audio_driven and self._audio_duration > 0 else self._duration_s

    def _caption_index_for_timeline(self, position: float) -> int:
        captions = self._CAPTIONS
        if not captions:
            return -1
        if self._caption_boundaries and len(self._caption_boundaries) == len(captions) + 1:
            for index in range(len(captions)):
                if position < self._caption_boundaries[index + 1] or index == len(captions) - 1:
                    return index
            return len(captions) - 1
        duration = max(0.001, self._timeline_duration)
        return min(len(captions) - 1, int(max(0.0, position) / duration * len(captions)))

    def _tick(self) -> None:
        if self._finished:
            return
        if self._audio_driven:
            if self._speech_position <= 0:
                return
            position = self._speech_position
        else:
            position = max(0.0, time.monotonic() - self._started_at)

        index = self._caption_index_for_timeline(position)
        if index >= 0 and index != self._last_caption_index:
            self._last_caption_index = index
            self.caption_changed.emit(self._CAPTIONS[index])
            if self._chapters:
                chapter = self._chapters[min(index, len(self._chapters) - 1)]
                self.chapter_changed.emit(chapter.focus, chapter.label, chapter.tab_index)
            else:
                self.chapter_changed.emit("greeting", "GREETING", -1)
        self.update()

        if self._audio_driven:
            if (
                self._speech_finished_at is not None
                and position >= self._audio_duration
                and time.monotonic() - self._speech_finished_at >= self._FINAL_HOLD_S
            ):
                self.finish()
        elif position >= self._duration_s + self._FINAL_HOLD_S:
            self.finish()

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        self.stop_speech()
        self.finished.emit()
        self.hide()

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        self.update()

    def set_spotlight(
        self,
        target: QRectF,
        label: str = "",
        shape: str = "rect",
        persistent_cutouts: tuple[QRectF, ...] = (),
    ) -> None:
        self._spotlight_target = QRectF(target)
        self._spotlight_label = str(label or "")
        self._spotlight_shape = "ellipse" if shape == "ellipse" else "rect"
        self._persistent_cutouts = [QRectF(item) for item in persistent_cutouts]
        self.update()

    def _current_spotlight_rect(self) -> QRectF:
        if self._reduced_motion:
            return QRectF(self._spotlight_target)
        return QRectF(self._spotlight_target)

    def _start_narration(self) -> None:
        if self._speech_thread and self._speech_thread.is_alive():
            return
        self._speech_stop.clear()
        cache_path = Path(_ui_symbol("_intro_voice_cache_path")(
            self._voice_name, self._narration, self._sequence_kind
        ))

        def _play_cached_or_render() -> None:
            try:
                if cache_path.is_file() and cache_path.stat().st_size:
                    pcm = cache_path.read_bytes()
                    duration = _pcm_duration_seconds(pcm)
                    boundaries = (
                        _load_intro_timing_cache(cache_path, len(self._CAPTIONS), duration)
                        if self._chapters else None
                    )
                    if boundaries is None and self._chapters:
                        boundaries = _intro_caption_boundaries(pcm, self._CAPTIONS)
                else:
                    if not self._api_key:
                        self._speech_error.emit("A verified Gemini key is required to play the introduction.")
                        return
                    if self._chapters:
                        pcm, boundaries = _generate_intro_aligned_speech_pcm(
                            self._CAPTIONS, self._voice_name, self._api_key
                        )
                    else:
                        pcm = _generate_intro_speech_pcm(
                            self._narration, self._voice_name, self._api_key
                        )
                        boundaries = None
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(pcm)
                    if boundaries is not None:
                        _write_intro_timing_cache(cache_path, boundaries)
                    duration = _pcm_duration_seconds(pcm)
                if not pcm:
                    raise RuntimeError("The introduction audio cache is empty.")
                self._speech_progress.emit(0.001)
                _ui_symbol("_play_intro_pcm")(
                    pcm,
                    progress_callback=lambda fraction: self._speech_progress.emit(
                        duration * fraction
                    ),
                    stop_event=self._speech_stop,
                )
                if not self._speech_stop.is_set():
                    self._speech_finished_signal.emit(duration)
            except Exception as exc:
                self._speech_error.emit(str(exc))

        self._speech_thread = threading.Thread(
            target=_play_cached_or_render,
            name="argus-intro-audio",
            daemon=True,
        )
        self._speech_thread.start()

    def stop_speech(self) -> None:
        self._speech_stop.set()

    def _on_speech_progress(self, position: float) -> None:
        self._speech_position = max(self._speech_position, float(position))
        self.update()

    def _on_speech_finished(self, duration: float) -> None:
        self._audio_duration = max(0.0, float(duration))
        self._speech_position = self._audio_duration
        self._speech_finished_at = time.monotonic()
        self.update()

    def _on_speech_error(self, message: str) -> None:
        self._speech_error_message = str(message)
        if not self._audio_driven:
            self.update()

    def paintEvent(self, _event) -> None:
        C = _ui_symbol("C")
        qcol = _ui_symbol("qcol")
        if C is None or qcol is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        spotlight = self._current_spotlight_rect()
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        if spotlight.isEmpty():
            pass
        else:
            if self._spotlight_shape == "ellipse":
                hole = QPainterPath()
                hole.addEllipse(spotlight)
                shade = shade.subtracted(hole)
            else:
                hole = QPainterPath()
                hole.addRoundedRect(spotlight, 8, 8)
                shade = shade.subtracted(hole)
        for cutout in self._persistent_cutouts:
            if not cutout.isEmpty():
                cutout_path = QPainterPath()
                cutout_path.addRoundedRect(cutout, 6, 6)
                shade = shade.subtracted(cutout_path)
        painter.fillPath(shade, qcol(C.BG, 96))

        current = self._caption_index_for_timeline(
            self._speech_position if self._audio_driven else time.monotonic() - self._started_at
        )
        caption = self._CAPTIONS[current] if current >= 0 else ""
        painter.setPen(QPen(QColor(C.PRI), 1))
        painter.setFont(_ui_symbol("QFont")(
            _ui_symbol("UI_FONT"),
            _ui_symbol("TOKENS").font_sizes["legacy_10"],
            _ui_symbol("QFont").Weight.Bold,
        ))
        painter.drawText(
            self.rect().adjusted(44, 34, -44, -100),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            caption,
        )
        if self._spotlight_label:
            painter.setPen(QPen(QColor(C.WHITE), 1))
            painter.drawText(
                QRectF(spotlight.left(), spotlight.bottom() + 8, max(180, spotlight.width()), 28),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._spotlight_label,
            )
        painter.end()

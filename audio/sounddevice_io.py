"""Sounddevice-based audio implementation for ARGUS.

This is the default audio backend that uses sounddevice for real microphone
and speaker I/O. Preserves exact behavior from main.py's _listen_audio,
_receive_audio, and _play_audio methods.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING, Callable, Optional

from audio.base import AudioConfig, AudioInterface
from config.settings import get_settings

if TYPE_CHECKING:
    import sounddevice as sd

logger = logging.getLogger("argus.audio")


def _sd():
    """Import sounddevice on first use; importing it starts PortAudio."""
    import sounddevice

    return sounddevice


class SounddeviceInputOutput(AudioInterface):
    """Sounddevice implementation of AudioInterface.

    Mirrors the exact audio handling from main.py:
    - InputStream callback in separate thread -> asyncio queue
    - RawOutputStream for playback
    - VAD/interruption handling via speaking lock
    - External audio passthrough support
    """

    def __init__(
        self,
        config: Optional[AudioConfig] = None,
        *,
        external_audio: bool = False,
        speaking_lock: Optional[threading.Lock] = None,
        is_speaking_ref: Optional[Callable[[], bool]] = None,
        set_speaking_cb: Optional[Callable[[bool], None]] = None,
        muted_cb: Optional[Callable[[], bool]] = None,
        shutdown_event: Optional[threading.Event] = None,
        turn_done_event: Optional[asyncio.Event] = None,
        audio_in_queue: Optional[asyncio.Queue] = None,
        out_queue: Optional[asyncio.Queue] = None,
        send_audio_cb: Optional[Callable[[bytes, str], None]] = None,
        tts_engine_check: Optional[Callable[[], bool]] = None,
    ):
        self._config = config or AudioConfig.from_settings(get_settings())
        self._external_audio = external_audio

        # Callbacks/refs to ArgusLive state (avoid circular dependency)
        self._speaking_lock = speaking_lock or threading.Lock()
        self._is_speaking_ref = is_speaking_ref or (lambda: False)
        self._set_speaking_cb = set_speaking_cb or (lambda v: None)
        self._muted_cb = muted_cb or (lambda: False)
        self._shutdown_event = shutdown_event or threading.Event()
        self._turn_done_event = turn_done_event
        self._audio_in_queue = audio_in_queue
        self._out_queue = out_queue
        self._send_audio_cb = send_audio_cb
        self._tts_engine_check = tts_engine_check or (lambda: False)

        # Internal state
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.RawOutputStream] = None
        self._input_callback: Optional[Callable[[bytes], None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking_ref()

    @property
    def input_active(self) -> bool:
        return self._input_stream is not None

    async def start_input(self, callback: Callable[[bytes], None]) -> None:
        """Start microphone input stream.

        The callback is called from the sounddevice thread and must be thread-safe.
        We bridge to asyncio using call_soon_threadsafe.
        """
        self._input_callback = callback
        self._loop = asyncio.get_event_loop()

        def sd_callback(indata, frames, time_info, status):
            if status:
                logger.info(f"[ARGUS] ⚠️ Mic status: {status}")
            with self._speaking_lock:
                argus_speaking = self._is_speaking_ref()
            if not argus_speaking and not self._muted_cb():
                data = indata.tobytes()
                if self._loop and not self._shutdown_event.is_set():
                    self._loop.call_soon_threadsafe(
                        self._safe_callback, data
                    )

        self._input_stream = _sd().InputStream(
            samplerate=self._config.send_sample_rate,
            channels=self._config.channels,
            dtype="int16",
            blocksize=self._config.chunk_size,
            callback=sd_callback,
        )
        self._input_stream.start()
        logger.info("[ARGUS] 🎤 Mic started")

    def _safe_callback(self, data: bytes) -> None:
        """Thread-safe callback wrapper."""
        if self._input_callback:
            try:
                self._input_callback(data)
            except Exception as e:
                logger.info(f"[ARGUS] ❌ Input callback error: {e}")

    async def start_output(self) -> None:
        """Start audio output stream."""
        if not self._external_audio:
            self._output_stream = _sd().RawOutputStream(
                samplerate=self._config.receive_sample_rate,
                channels=self._config.channels,
                dtype="int16",
                blocksize=self._config.chunk_size,
            )
            self._output_stream.start()
        logger.info("[ARGUS] 🔊 Play started")

    async def stop(self) -> None:
        """Stop both streams and cleanup."""
        self._shutdown_event.set()

        if self._input_stream is not None:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception as e:
                logger.info(f"[ARGUS] ⚠️ Input stream close error: {e}")
            self._input_stream = None

        if self._output_stream is not None:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception as e:
                logger.info(f"[ARGUS] ⚠️ Output stream close error: {e}")
            self._output_stream = None

        self._set_speaking_cb(False)
        logger.info("[ARGUS] 🔇 Audio stopped")

    def put_audio(self, chunk: bytes) -> None:
        """Queue audio chunk for playback (called from receive loop)."""
        if self._audio_in_queue is not None:
            try:
                self._audio_in_queue.put_nowait(chunk)
            except asyncio.QueueFull:
                logger.warning("[ARGUS] ⚠️ Audio queue full, dropping chunk")

    async def get_audio(self) -> Optional[bytes]:
        """Get next audio chunk for playback."""
        if self._audio_in_queue is None:
            return None

        try:
            _audio_get_t0 = time.perf_counter()
            chunk = await asyncio.wait_for(
                self._audio_in_queue.get(),
                timeout=0.1
            )
            # Record audio latency metric
            try:
                from observability.metrics import metrics
                metrics.record_audio_latency(time.perf_counter() - _audio_get_t0)
            except Exception:
                pass
            return chunk
        except asyncio.TimeoutError:
            # Check for turn completion
            if (
                self._turn_done_event
                and self._turn_done_event.is_set()
                and self._audio_in_queue.empty()
            ):
                self._set_speaking_cb(False)
                self._turn_done_event.clear()
            return None
        except Exception as e:
            logger.info(f"[ARGUS] ❌ Get audio error: {e}")
            raise

    async def play_loop(self) -> None:
        """Main playback loop - call this from ArgusLive._play_audio equivalent.

        Handles:
        - External TTS passthrough
        - Speaking state management
        - Stream writing
        """
        while not self._shutdown_event.is_set():
            chunk = await self.get_audio()
            if chunk is None:
                continue

            # Skip Gemini audio when external TTS is active
            if self._tts_engine_check() and self._external_audio:
                continue  # drain silently

            self._set_speaking_cb(True)

            if self._external_audio:
                if self._send_audio_cb:
                    try:
                        self._send_audio_cb(
                            chunk,
                            f"audio/pcm;rate={self._config.receive_sample_rate}"
                        )
                    except Exception as e:
                        logger.info(f"[ARGUS] ❌ External audio send error: {e}")
            elif self._output_stream is not None:
                try:
                    await asyncio.to_thread(self._output_stream.write, chunk)
                except Exception as e:
                    logger.info(f"[ARGUS] ❌ Audio write error: {e}")
                    raise

    async def send_realtime_loop(self) -> None:
        """Send realtime audio to Gemini - call from ArgusLive._send_realtime equivalent."""
        while not self._shutdown_event.is_set():
            if self._out_queue is None:
                return
            try:
                msg = await self._out_queue.get()
                if msg is None:
                    return
                # This would need session access - handled by ArgusLive
                # Kept for interface completeness
            except Exception:
                return
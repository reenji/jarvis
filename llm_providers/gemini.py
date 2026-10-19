"""Gemini Live provider backed by the supported google-genai SDK."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from llm_providers.base import (
    BaseLLM,
    LLMAuthenticationError,
    LLMConfig,
    LLMConnectionError,
    LLMEvent,
    LLMEventType,
    LLMTransientError,
    LLMUnsupportedVoiceError,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger("argus.llm.gemini")


class GeminiLLM(BaseLLM):
    """Gemini Live API implementation of :class:`BaseLLM`."""

    def __init__(
        self,
        api_key: str,
        http_options: dict[str, Any] | None = None,
        max_retries: int = 0,
        retry_delay: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._http_options = types.HttpOptions(
            **(http_options or {"api_version": "v1beta"})
        )
        self._client: genai.Client | None = None
        self._connection: Any = None
        self._session: Any = None
        self._connected = False
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def connect(self, config: LLMConfig) -> None:
        """Open a Gemini Live session using the provider-neutral config with retry."""
        attempt = 0
        while self._max_retries == 0 or attempt < self._max_retries:
            try:
                self._client = genai.Client(
                    api_key=self._api_key,
                    http_options=self._http_options,
                )
                self._connection = self._client.aio.live.connect(
                    model=config.model,
                    config=self._build_live_config(config),
                )

                try:
                    self._session = await self._connection.__aenter__()
                    self._connected = True
                except Exception as exc:
                    self._session = None
                    self._connection = None
                    self._connected = False
                    classification = self.classify_error(exc)
                    if classification == "transient":
                        if self._max_retries > 0 and attempt + 1 >= self._max_retries:
                            self._raise_provider_error(
                                "Failed to connect to Gemini Live after retries", exc
                            )
                        await asyncio.sleep(
                            self._retry_delay
                            * (2**attempt)
                            * (1 + self._retry_jitter())
                        )
                        attempt += 1
                        continue
                    self._raise_provider_error("Failed to connect to Gemini Live", exc)
                break
            except Exception as exc:
                classification = self.classify_error(exc)
                if classification == "transient":
                    if self._max_retries > 0 and attempt + 1 >= self._max_retries:
                        self._raise_provider_error(
                            "Failed to connect to Gemini Live after retries", exc
                        )
                    await asyncio.sleep(
                        self._retry_delay * (2**attempt) * (1 + self._retry_jitter())
                    )
                    attempt += 1
                    continue
                self._raise_provider_error("Failed to connect to Gemini Live", exc)

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert neutral function declarations to Gemini declarations."""
        declarations = []
        for tool in tools:
            if not tool.get("name"):
                continue
            declarations.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "parameters",
                        {"type": "OBJECT", "properties": {}},
                    ),
                }
            )
        return declarations

    @classmethod
    def _build_live_config(cls, config: LLMConfig) -> types.LiveConnectConfig:
        declarations = cls._convert_tools(config.tools)
        return types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=config.system_instruction,
            tools=([{"function_declarations": declarations}] if declarations else []),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=(
                        types.StartSensitivity.START_SENSITIVITY_HIGH
                    ),
                    end_of_speech_sensitivity=(
                        types.EndSensitivity.END_SENSITIVITY_HIGH
                    ),
                    silence_duration_ms=config.vad_silence_ms,
                )
            ),
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=config.voice_name
                    )
                )
            ),
        )

    async def send_audio(
        self,
        audio_data: bytes,
        mime_type: str = "audio/pcm;rate=16000",
    ) -> None:
        session = self._require_session()
        await session.send_realtime_input(
            media={"data": audio_data, "mime_type": mime_type}
        )

    async def send_text(self, text: str) -> None:
        session = self._require_session()
        await session.send_client_content(
            turns={"parts": [{"text": text}]},
            turn_complete=True,
        )

    async def send_tool_result(self, result: ToolResult) -> None:
        session = self._require_session()
        response_text = (
            f"Error: {result.error}" if result.error is not None else result.result
        )
        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=result.id,
                    name=result.name,
                    response={"result": response_text},
                )
            ]
        )

    async def receive(self) -> AsyncIterator[LLMEvent]:
        """Yield normalized events received from the model with retry and timeout."""
        attempt = 0
        while self._max_retries == 0 or attempt < self._max_retries:
            try:
                timeout = self._retry_delay * (2**attempt) * (1 + self._retry_jitter())
                async for event in self._receive_with_timeout(timeout):
                    yield event
                break
            except asyncio.TimeoutError:
                if self._max_retries > 0 and attempt + 1 >= self._max_retries:
                    yield LLMEvent(
                        type=LLMEventType.ERROR,
                        data="Receive timeout after max retries",
                    )
                    return
                await asyncio.sleep(
                    self._retry_delay * (2**attempt) * (1 + self._retry_jitter())
                )
                attempt += 1
                continue
            except Exception as exc:
                classification = self.classify_error(exc)
                if classification == "normal_close":
                    yield LLMEvent(type=LLMEventType.CLOSE)
                    return
                if classification == "transient":
                    if self._max_retries > 0 and attempt + 1 >= self._max_retries:
                        yield LLMEvent(
                            type=LLMEventType.ERROR,
                            data="Transient error after max retries",
                        )
                        return
                    await asyncio.sleep(
                        self._retry_delay * (2**attempt) * (1 + self._retry_jitter())
                    )
                    attempt += 1
                    continue
                yield LLMEvent(type=LLMEventType.ERROR, data=exc)
                raise

    async def _receive_with_timeout(self, timeout: float) -> AsyncIterator[LLMEvent]:
        """Iterate session.receive() with a wall-clock timeout, yielding normalized events."""
        deadline = asyncio.get_event_loop().time() + timeout
        session = self._require_session()
        try:
            async for response in session.receive():
                if asyncio.get_event_loop().time() > deadline:
                    raise asyncio.TimeoutError("Receive timed out")
                # Normalize the response into LLMEvent(s)
                server_content = getattr(response, "server_content", None)
                model_turn = getattr(server_content, "model_turn", None)
                if model_turn:
                    for part in model_turn.parts or []:
                        inline_data = getattr(part, "inline_data", None)
                        if inline_data and inline_data.data:
                            yield LLMEvent(
                                type=LLMEventType.AUDIO,
                                data=inline_data.data,
                            )

                        text = getattr(part, "text", None)
                        if text:
                            yield LLMEvent(type=LLMEventType.TEXT, data=text)

                if server_content:
                    for field_name, metadata in (
                        ("output_transcription", {"is_output": True}),
                        ("input_transcription", {"is_input": True}),
                    ):
                        transcription = getattr(server_content, field_name, None)
                        text = getattr(transcription, "text", None)
                        if text:
                            yield LLMEvent(
                                type=LLMEventType.TEXT,
                                data=text,
                                metadata=metadata,
                            )

                    if getattr(server_content, "turn_complete", False):
                        yield LLMEvent(type=LLMEventType.TURN_COMPLETE)

                    if getattr(server_content, "interrupted", False):
                        yield LLMEvent(type=LLMEventType.INTERRUPTION)

                tool_call = getattr(response, "tool_call", None)
                for function_call in getattr(tool_call, "function_calls", []) or []:
                    yield LLMEvent(
                        type=LLMEventType.TOOL_CALL,
                        data=ToolCall(
                            id=str(function_call.id or ""),
                            name=function_call.name,
                            args=dict(function_call.args or {}),
                        ),
                    )
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            raise exc

    async def close(self) -> None:
        connection = self._connection
        self._connection = None
        self._session = None
        self._connected = False
        if connection is not None:
            await connection.__aexit__(None, None, None)

    def is_connected(self) -> bool:
        return self._connected

    @staticmethod
    def classify_error(error: Exception) -> str:
        """Classify common Gemini API errors for reconnect decisions."""
        message = str(error).lower()
        status = getattr(error, "code", None)
        if status is None:
            status = getattr(error, "status_code", None)

        if "1000" in message:
            return "normal_close"
        if "voice" in message and any(
            phrase in message for phrase in ("not available", "unsupported", "invalid")
        ):
            return "unsupported_voice"
        if status in {401, 403} or any(
            marker in message
            for marker in ("api key", "unauthenticated", "permission denied")
        ):
            return "permanent"
        if status == 429 or (isinstance(status, int) and status >= 500):
            return "transient"
        if any(
            marker in message
            for marker in ("timeout", "temporarily unavailable", "connection reset")
        ):
            return "transient"
        return "permanent"

    def _require_session(self) -> Any:
        if not self._connected or self._session is None:
            raise LLMConnectionError("Not connected to Gemini Live")
        return self._session

    def _retry_jitter(self) -> float:
        """Return jitter factor in [0, retry_jitter_ratio] for backoff delay."""
        return random.random() * self._retry_delay / 10.0

    def _raise_provider_error(self, message: str, error: Exception) -> None:
        classification = self.classify_error(error)
        if classification == "unsupported_voice":
            raise LLMUnsupportedVoiceError(f"{message}: {error}") from error
        if classification == "permanent" and any(
            marker in str(error).lower()
            for marker in ("api key", "unauthenticated", "permission denied")
        ):
            raise LLMAuthenticationError(f"{message}: {error}") from error
        if classification == "transient":
            raise LLMTransientError(f"{message}: {error}") from error
        raise LLMConnectionError(f"{message}: {error}") from error

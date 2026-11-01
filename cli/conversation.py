"""Text-only Gemini conversation with the existing ARGUS tool registry."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cli.client import TerminalClient
from cli.history import SessionStore


def _content_to_json(content: Any) -> dict[str, Any]:
    if hasattr(content, "model_dump"):
        return content.model_dump(mode="json", exclude_none=True)
    if isinstance(content, dict):
        return content
    raise TypeError("Gemini returned a conversation item that cannot be stored")


class TextConversation:
    """A resumable text session; the Google SDK and tools load on demand."""

    MAX_TOOL_ROUNDS = 8

    def __init__(
        self,
        session_id: str,
        store: SessionStore,
        *,
        client: Any | None = None,
        registry: Any | None = None,
        terminal: TerminalClient | None = None,
        model: str | None = None,
        system_instruction: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.store = store
        self._types = None
        self._model_client = client or self._create_model_client()
        self._registry = registry or self._create_registry()
        self.terminal = terminal or TerminalClient()
        self.model = model or self._configured_model()
        self.last_usage: dict[str, int] = {}
        self.last_duration_seconds = 0.0
        self.system_instruction = system_instruction or self._build_system_instruction()
        self._tool_context = self._create_tool_context()
        self.history = self._restore_history(store.load_history(session_id))

    @staticmethod
    def _create_model_client():
        from google import genai

        from config.settings import get_api_key

        return genai.Client(api_key=get_api_key())

    @staticmethod
    def _create_registry():
        from tools.registry import registry

        return registry

    @staticmethod
    def _configured_model() -> str:
        override = os.environ.get("ARGUS_CLI_MODEL")
        if override:
            return override
        from config.settings import get_settings

        return get_settings().llm.model

    def _create_tool_context(self):
        from tools.registry import ToolContext

        return ToolContext(
            client=self.terminal,
            speak=lambda _text: False,
            speak_vision_result=lambda _text: False,
        )

    def _build_system_instruction(self) -> str:
        prompt_path = Path(__file__).resolve().parent.parent / "core" / "prompt.txt"
        prompt = prompt_path.read_text(encoding="utf-8")
        try:
            from memory.memory_manager import format_memory_for_prompt, load_memory

            memory = format_memory_for_prompt(load_memory())
        except Exception:
            memory = ""
        now = datetime.now().astimezone().strftime("%A, %B %d, %Y — %I:%M %p %Z")
        parts = [f"[CURRENT DATE & TIME]\nRight now it is: {now}.\n"]
        if memory:
            parts.append(f"[USER MEMORY]\n{memory}\n")
        parts.append(prompt)
        return "\n\n".join(parts)

    def _restore_history(self, history: list[dict[str, Any]]) -> list[Any]:
        from google.genai import types

        self._types = types
        restored = []
        for item in history:
            try:
                restored.append(types.Content.model_validate(item))
            except Exception:
                # Skip one damaged history item while keeping the rest usable.
                continue
        return restored

    def _save_history(self) -> None:
        self.store.save_history(
            self.session_id,
            [_content_to_json(item) for item in self.history],
        )

    def _generate_config(self):
        from google.genai import types

        declarations = self._registry.declarations()
        # The terminal has no ARGUS window whose theme or docking state can change.
        declarations = [
            declaration
            for declaration in declarations
            if declaration.get("name") not in {"graphics_quality", "argus_ui_control"}
        ]
        tools = [types.Tool(function_declarations=declarations)] if declarations else []
        return types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    async def _generate(self, *, on_text=None):
        config = self._generate_config()
        if on_text is None:
            return await self._generate_non_streaming(config)

        async_client = getattr(self._model_client, "aio", None)
        models = getattr(async_client, "models", None)
        stream_factory = getattr(models, "generate_content_stream", None)
        if not callable(stream_factory):
            response = await self._generate_non_streaming(config)
            content = self._candidate_content(response)
            answer_text = self._response_text(response, content)
            if answer_text:
                on_text(answer_text)
            return response

        stream = await stream_factory(
            model=self.model,
            contents=self.history,
            config=config,
        )
        text_chunks: list[str] = []
        function_calls: dict[tuple[str | None, str], dict[str, Any]] = {}
        other_parts = []
        role = "model"
        usage_metadata = None
        async for chunk in stream:
            chunk_usage = getattr(chunk, "usage_metadata", None)
            if chunk_usage is not None:
                usage_metadata = chunk_usage
            content = self._candidate_content(chunk)
            if content is not None:
                role = str(getattr(content, "role", None) or role)
            chunk_text = str(getattr(chunk, "text", None) or "")
            if not chunk_text and content is not None:
                chunk_text = "\n".join(
                    str(getattr(part, "text", "") or "")
                    for part in (getattr(content, "parts", None) or [])
                    if getattr(part, "text", None)
                )
            if chunk_text:
                text_chunks.append(chunk_text)
                on_text(chunk_text)
            for part in (getattr(content, "parts", None) or []) if content is not None else []:
                function_call = getattr(part, "function_call", None)
                if function_call is not None and getattr(function_call, "name", None):
                    key = (getattr(function_call, "id", None), str(function_call.name))
                    entry = function_calls.setdefault(
                        key,
                        {"name": str(function_call.name), "args": {}},
                    )
                    entry["args"].update(dict(getattr(function_call, "args", None) or {}))
                elif not getattr(part, "text", None):
                    other_parts.append(part)

        full_text = "".join(text_chunks).strip()
        parts = []
        if full_text:
            parts.append(self._types.Part(text=full_text))
        for (call_id, _name), value in function_calls.items():
            call_fields = {"name": value["name"], "args": value["args"]}
            if call_id:
                call_fields["id"] = call_id
            parts.append(self._types.Part(function_call=self._types.FunctionCall(**call_fields)))
        parts.extend(other_parts)
        combined = self._types.Content(role=role, parts=parts)
        return SimpleNamespace(
            text=full_text or None,
            candidates=[SimpleNamespace(content=combined)],
            usage_metadata=usage_metadata,
        )

    async def _generate_non_streaming(self, config):
        return await asyncio.to_thread(
            self._model_client.models.generate_content,
            model=self.model,
            contents=self.history,
            config=config,
        )

    @staticmethod
    def _candidate_content(response):
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is not None:
                return content
        return None

    @staticmethod
    def _function_calls(content) -> list[Any]:
        calls = []
        for part in getattr(content, "parts", None) or []:
            function_call = getattr(part, "function_call", None)
            if function_call is not None and getattr(function_call, "name", None):
                calls.append(function_call)
        return calls

    @staticmethod
    def _response_text(response, content) -> str:
        text = getattr(response, "text", None)
        if text:
            return str(text).strip()
        return "\n".join(
            str(getattr(part, "text", "") or "").strip()
            for part in (getattr(content, "parts", None) or [])
            if getattr(part, "text", None)
        ).strip()

    @staticmethod
    def _usage_summary(response) -> dict[str, int]:
        metadata = getattr(response, "usage_metadata", None)
        if metadata is None:
            return {}
        fields = {
            "input_tokens": "prompt_token_count",
            "output_tokens": "candidates_token_count",
            "total_tokens": "total_token_count",
        }
        summary = {}
        for key, attribute in fields.items():
            value = getattr(metadata, attribute, None)
            if value is not None:
                try:
                    summary[key] = int(value)
                except (TypeError, ValueError, OverflowError):
                    continue
        return summary

    async def _run_tool(self, function_call) -> dict[str, Any]:
        name = str(function_call.name)
        args = dict(getattr(function_call, "args", None) or {})
        self.terminal.write_log(f"SYS: Executing {name}.")
        try:
            result = await self._registry.execute(
                name=name,
                ctx=self._tool_context,
                args=args,
            )
            self.terminal.write_log(f"SYS: Finished {name}.")
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as exc:
            self.terminal.write_log(f"ERR: {name} — {str(exc)[:180]}")
            return {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}

    async def ask(self, text: str, *, on_text=None) -> str:
        user_text = str(text or "").strip()
        if not user_text:
            raise ValueError("A pergunta não pode estar vazia.")
        from google.genai import types

        if self._types is None:
            self._types = types
        started_at = time.perf_counter()
        self.last_usage = {}
        turn_start = len(self.history)
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
        self._save_history()
        try:
            return await self._complete_turn(on_text=on_text)
        except asyncio.CancelledError:
            del self.history[turn_start:]
            self._save_history()
            raise
        finally:
            self.last_duration_seconds = time.perf_counter() - started_at

    async def _complete_turn(self, *, on_text=None) -> str:
        types = self._types
        for _round in range(self.MAX_TOOL_ROUNDS + 1):
            response = await self._generate(on_text=on_text)
            content = self._candidate_content(response)
            if content is None:
                raise RuntimeError("O Gemini retornou uma resposta sem conteúdo.")
            calls = self._function_calls(content)
            if not calls:
                self.last_usage = self._usage_summary(response)
                self.history.append(content)
                self._save_history()
                answer = self._response_text(response, content)
                return answer or "Não recebi uma resposta em texto."

            self.history.append(content)
            self._save_history()
            results = []
            for function_call in calls:
                result = await self._run_tool(function_call)
                call_id = getattr(function_call, "id", None)
                function_response = types.FunctionResponse(
                    name=function_call.name,
                    response=result,
                    **({"id": call_id} if call_id else {}),
                )
                part = types.Part(function_response=function_response)
                results.append(part)
            self.history.append(types.Content(role="user", parts=results))
            self._save_history()

        raise RuntimeError("O Argus atingiu o limite de chamadas de ferramentas nesta resposta.")

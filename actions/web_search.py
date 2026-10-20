"""Grounded web search through Gemini, without scraping search-engine pages."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_WEB_SEARCH_MODEL = "gemini-3.8-flash"


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_api_key() -> str:
    from memory.config_manager import get_gemini_key

    stored_key = get_gemini_key()
    if stored_key:
        return stored_key
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            key = data.get("gemini_api_key") or data.get("GEMINI_API_KEY")
            if key:
                return key
    except Exception:
        pass

    raise ValueError(
        "Gemini API key not found. Set GEMINI_API_KEY or "
        "config/api_keys.json['gemini_api_key']."
    )


def _source_url_is_valid(uri: str) -> bool:
    parsed = urlparse(str(uri or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _response_text(response) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
    return "\n".join(
        str(part.text).strip() for part in parts if getattr(part, "text", None)
    ).strip()


def _grounding_sources(response) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        metadata = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(metadata, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = str(getattr(web, "uri", "") or "").strip()
            if not _source_url_is_valid(uri) or any(item["url"] == uri for item in sources):
                continue
            sources.append({
                "title": str(getattr(web, "title", "") or uri).strip(),
                "url": uri,
            })
    return sources


def _is_model_not_found(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(marker in message for marker in (
        "404", "not_found", "not found", "no longer available", "unknown model",
    ))


def _gemini_grounded_search(query: str, *, client=None) -> tuple[str, list[dict[str, str]]]:
    """Use Google's supported Search grounding API and return its cited URLs."""
    from google import genai
    from google.genai import types

    if client is None:
        client = genai.Client(
            api_key=_get_api_key(),
            http_options=types.HttpOptions(timeout=25_000),
        )

    configured_model = (
        os.environ.get("ARGUS_WEB_SEARCH_MODEL", DEFAULT_WEB_SEARCH_MODEL).strip()
        or DEFAULT_WEB_SEARCH_MODEL
    )

    def generate(model: str):
        return client.models.generate_content(
            model=model,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

    try:
        response = generate(configured_model)
    except Exception as exc:
        # Older installs may still carry gemini-2.5-flash in the environment.
        # Recover only from a removed/unavailable model, with one current-model
        # retry; never fall back to scraping search-engine pages.
        if configured_model == DEFAULT_WEB_SEARCH_MODEL or not _is_model_not_found(exc):
            raise
        print(
            f"[WebSearch] Configured model {configured_model!r} is unavailable; "
            f"retrying once with {DEFAULT_WEB_SEARCH_MODEL!r}."
        )
        response = generate(DEFAULT_WEB_SEARCH_MODEL)

    answer = _response_text(response)
    if not answer:
        raise ValueError("Gemini returned an empty response.")
    return answer, _grounding_sources(response)


def _format_grounded_answer(answer: str, sources: list[dict[str, str]]) -> str:
    if not sources:
        return answer
    source_lines = "\n".join(
        f"- {source['title']}: {source['url']}" for source in sources[:8]
    )
    return f"{answer}\n\nFontes consultadas:\n{source_lines}"


def _gemini_search(query: str) -> str:
    answer, sources = _gemini_grounded_search(query)
    return _format_grounded_answer(answer, sources)


def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Use current, source-grounded facts and identify meaningful uncertainty."
    )
    return _gemini_search(query)


def web_search(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query = str(params.get("query", "") or "").strip()
    mode = str(params.get("mode", "search") or "search").lower().strip()
    items = params.get("items", []) or []
    aspect = str(params.get("aspect", "general") or "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."
    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(map(str, items))}")

    print(f"[WebSearch] Query: {query!r}  Mode: {mode}")
    try:
        if mode == "compare" and items:
            return _compare([str(item) for item in items], aspect)
        return _gemini_search(query)
    except Exception as exc:
        print(f"[WebSearch] Gemini grounded search failed: {exc}")
        return (
            f"A pesquisa falhou no Gemini Search: {exc}. "
            "Não fiz buscas automatizadas em outros mecanismos nem abri um navegador."
        )

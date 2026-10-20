#web_search.py
import json
import os
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
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

    raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or config/api_keys.json['gemini_api_key'].")


def _gemini_search(query: str) -> str:
    from google import genai
    from google.genai import types

    client   = genai.Client(
        api_key=_get_api_key(),
        http_options=types.HttpOptions(timeout=25_000),
    )
    response = client.models.generate_content(
        model=os.environ.get("ARGUS_WEB_SEARCH_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash",
        contents=query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    text = str(getattr(response, "text", "") or "").strip()
    candidates = getattr(response, "candidates", None) or []
    if not text and candidates:
        parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
        text = "\n".join(
            str(part.text).strip()
            for part in parts
            if getattr(part, "text", None)
        ).strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")

    # Google grounding supplies source links separately from the answer text.
    sources: list[tuple[str, str]] = []
    if candidates:
        metadata = getattr(candidates[0], "grounding_metadata", None)
        for chunk in getattr(metadata, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = str(getattr(web, "uri", "") or "").strip()
            title = str(getattr(web, "title", "") or uri).strip()
            if uri and all(uri != existing_uri for _, existing_uri in sources):
                sources.append((title, uri))
    if sources:
        text += "\n\nFontes consultadas:\n" + "\n".join(
            f"- {title}: {uri}" for title, uri in sources[:8]
        )
    return text


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    from ddgs import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title":   r.get("title",  ""),
                "snippet": r.get("body",   ""),
                "url":     r.get("href",   ""),
            })
    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"Não consegui recuperar resultados online para: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )
    try:
        return _gemini_search(query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini compare failed: {e} — falling back to DDG")

    # DDG fallback: fetch results per item and merge
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
    if not any(all_results.values()):
        return "Não consegui obter resultados para comparar. A busca Gemini falhou e o provedor DDG não retornou resultados."
    return "\n".join(lines)

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 Query: {query!r}  Mode: {mode}")

    try:
        if mode == "compare" and items:
            print(f"[WebSearch] 📊 Comparing: {items}")
            result = _compare(items, aspect)
            print("[WebSearch] ✅ Compare done.")
            return result

        print("[WebSearch] 🌐 Trying Gemini...")
        try:
            result = _gemini_search(query)
            print("[WebSearch] ✅ Gemini OK.")
            return result
        except Exception as e:
            print(f"[WebSearch] ⚠️ Gemini failed ({e}) — trying DDG...")
            results = _ddg_search(query)
            result  = _format_ddg(query, results)
            print(f"[WebSearch] ✅ DDG: {len(results)} result(s).")
            if not results:
                return (
                    f"Não consegui pesquisar '{query}': o Gemini Search falhou e o DDG não retornou resultados. "
                    "Verifique a conexão e a configuração da chave Gemini."
                )
            return result

    except Exception as e:
        print(f"[WebSearch] ❌ All backends failed: {e}")
        return f"A pesquisa falhou: {e}"

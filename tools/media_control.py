from __future__ import annotations

from typing import Any

declaration: dict[str, Any] = {"name": "media_control", "description": "Controls music playback, primarily Spotify. Use when the user asks to play, resume, pause, stop, toggle, skip, or go back in Spotify, Apple Music, YouTube Music, or the active media player. Spotify is the default platform. Pass a song, artist, album, playlist, or Spotify link in query. When a plain Spotify search opens results, immediately use computer_control screen_click to select the matching visible track; do not ask the user to choose it.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "enum": ["play", "pause", "stop", "toggle", "next", "previous", "play_query"], "description": "Playback command. Use play_query to find a specific song or other item."}, "platform": {"type": "STRING", "enum": ["spotify", "apple_music", "youtube_music", "system"], "description": "Music platform. Default: spotify."}, "query": {"type": "STRING", "description": "Song, artist, album, playlist, or Spotify link for play/play_query."}}, "required": ["action"]}}

async def execute(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    from tools.impl import execute as _execute
    return await _execute(ctx, "media_control", args)

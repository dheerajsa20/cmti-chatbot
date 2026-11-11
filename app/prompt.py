"""Builds the messages sent to the model: system prompt (four customization layers) + memory + new message.

The knowledge and prompt are read from files every time they change, so editing knowledge/knowledge.md
updates the bot without restarting or changing code.
"""
from pathlib import Path

from app.config import settings

_cache: dict[Path, tuple[float, str]] = {}


def _read(path: Path) -> str:
    mtime = path.stat().st_mtime
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    text = path.read_text(encoding="utf-8")
    _cache[path] = (mtime, text)
    return text


def system_prompt() -> str:
    return _read(settings.prompt_path).replace("{knowledge}", _read(settings.knowledge_path).strip())


def build_messages(history: list[dict], user_message: str) -> list[dict]:
    """history: earlier messages from the database ({'role': 'user'|'bot', 'content': ...}), oldest first."""
    messages = [{"role": "system", "content": system_prompt()}]
    for item in history:
        messages.append({"role": "assistant" if item["role"] == "bot" else "user", "content": item["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages

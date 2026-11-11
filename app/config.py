"""Settings, read from environment variables (and a local .env file in development)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # A low-cost model tier, as the brief requires. Change it in .env without touching code.
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "400"))
    request_timeout_s: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
    history_turns: int = int(os.getenv("HISTORY_TURNS", "8"))  # user+bot pairs sent back as memory
    max_message_chars: int = int(os.getenv("MAX_MESSAGE_CHARS", "1000"))
    knowledge_path: Path = ROOT / os.getenv("KNOWLEDGE_FILE", "knowledge/knowledge.md")
    prompt_path: Path = ROOT / os.getenv("PROMPT_FILE", "knowledge/system_prompt.md")
    database_path: Path = ROOT / os.getenv("DATABASE_FILE", "data/chatbot.db")
    # Websites allowed to call the API from a browser (the CMTI site and local testing).
    allowed_origins: list[str] = field(default_factory=lambda: _list(
        "ALLOWED_ORIGINS", "https://dheerajsa20.github.io,http://localhost:8000,http://127.0.0.1:8000"))


settings = Settings()

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    discord_token: str
    app_guild_id: int | None
    ai_api_key: str | None
    ai_base_url: str
    ai_model: str
    database_path: str
    channel_bootstrap_file: str | None
    enable_message_content: bool
    ffmpeg_path: str


def load_settings() -> Settings:
    guild_id_raw = os.getenv("APP_GUILD_ID", "").strip()
    return Settings(
        discord_token=os.getenv("MTUyMTUwOTg3NTc1NzM1MDkzMg.G5X_eV.4OCOFfjkhqjb81-QYTfGY1xwIZjgwzjUn0Ok6Q", "").strip(),
        app_guild_id=int(guild_id_raw) if guild_id_raw else None,
        ai_api_key=os.getenv("AI_API_KEY", "").strip() or None,
        ai_base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip(),
        ai_model=os.getenv("AI_MODEL", "gpt-4.1-mini").strip(),
        database_path=os.getenv("DATABASE_PATH", "rp_master.sqlite3").strip(),
        channel_bootstrap_file=os.getenv("CHANNEL_BOOTSTRAP_FILE", "").strip() or None,
        enable_message_content=_as_bool(os.getenv("ENABLE_MESSAGE_CONTENT"), False),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg").strip(),
    )

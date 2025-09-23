import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    token: str
    guild_id: int | None
    channel_id: int | None
    admin_ids: list[int]
    database_path: str


def get_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "")
    guild_id = int(os.getenv("GUILD_ID", "0")) or None
    channel_id = int(os.getenv("CHANNEL_ID", "0")) or None
    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
    admin_ids = [int(x) for x in admin_ids_raw.split(",") if x.strip().isdigit()]
    database_path = os.getenv("DATABASE_PATH", "whitelist.db")

    if not token:
        raise RuntimeError("DISCORD_TOKEN is required in .env")

    return Settings(
        token=token,
        guild_id=guild_id,
        channel_id=channel_id,
        admin_ids=admin_ids,
        database_path=database_path,
    )

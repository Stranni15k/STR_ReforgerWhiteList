import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    token: str
    guild_id: int | None
    channel_id: int | None
    admin_channel_id: int | None
    admin_role_id: int | None
    database_path: str


def get_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "")
    guild_id = int(os.getenv("GUILD_ID", "0")) or None
    channel_id = int(os.getenv("CHANNEL_ID", "0")) or None
    admin_channel_id = int(os.getenv("ADMIN_CHANNEL_ID", "0")) or None
    admin_role_id = int(os.getenv("ADMIN_ROLE", "0")) or None
    database_path = os.getenv("DATABASE_PATH", "whitelist.db")

    if not token:
        raise RuntimeError("DISCORD_TOKEN is required in .env")

    return Settings(
        token=token,
        guild_id=guild_id,
        channel_id=channel_id,
        admin_channel_id=admin_channel_id,
        admin_role_id=admin_role_id,
        database_path=database_path,
    )

import os
from dataclasses import dataclass
from typing import Optional, List


def get_env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def parse_int_list(env_val: Optional[str]) -> List[int]:
    if not env_val:
        return []
    parts = [p.strip() for p in env_val.split(",") if p.strip()]
    ints: List[int] = []
    for p in parts:
        try:
            ints.append(int(p))
        except ValueError:
            continue
    return ints


@dataclass
class Settings:
    token: str
    data_path: str = "/data"
    log_level: str = "INFO"
    allowed_guilds: List[int] = None  # type: ignore

    @staticmethod
    def load() -> "Settings":
        token = get_env("DISCORD_TOKEN", required=True)
        # Support DATA_DIR alias; prefer DATA_DIR, fallback to DATA_PATH
        data_path = get_env("DATA_DIR", None) or get_env("DATA_PATH", "/data") or "/data"
        log_level = get_env("LOG_LEVEL", "INFO") or "INFO"
        allowed_guilds = parse_int_list(get_env("ALLOWED_GUILDS"))
        return Settings(token=token, data_path=data_path, log_level=log_level, allowed_guilds=allowed_guilds)

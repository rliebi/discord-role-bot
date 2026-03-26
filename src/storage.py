import json
import os
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class GuildConfig:
    guild_id: int
    admin_user_id: Optional[int] = None
    moderator_role_id: Optional[int] = None
    moderator_user_ids: list[int] = field(default_factory=list)
    allowed_role_ids: list[int] = field(default_factory=list)
    assignment_channel_id: Optional[int] = None
    role_parents: Dict[int, int] = field(default_factory=dict)  # Mapping: child_role_id -> parent_role_id
    xor_groups: Dict[str, list[int]] = field(default_factory=dict)  # Group name -> list of role IDs

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "GuildConfig":
        return GuildConfig(
            guild_id=int(data["guild_id"]),
            admin_user_id=data.get("admin_user_id"),
            moderator_role_id=data.get("moderator_role_id"),
            moderator_user_ids=list(data.get("moderator_user_ids", [])),
            allowed_role_ids=list(data.get("allowed_role_ids", [])),
            assignment_channel_id=data.get("assignment_channel_id"),
            role_parents={int(k): int(v) for k, v in data.get("role_parents", {}).items()},
            xor_groups={str(k): [int(rid) for rid in v] for k, v in data.get("xor_groups", {}).items()},
        )


class Storage:
    def __init__(self, root: str):
        self.root = root
        self.guilds_dir = os.path.join(self.root, "guilds")
        os.makedirs(self.guilds_dir, exist_ok=True)

    def _guild_path(self, guild_id: int) -> str:
        return os.path.join(self.guilds_dir, f"{guild_id}.json")

    def load_guild(self, guild_id: int) -> GuildConfig:
        path = self._guild_path(guild_id)
        if not os.path.exists(path):
            cfg = GuildConfig(guild_id=guild_id)
            self.save_guild(cfg)
            return cfg
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return GuildConfig.from_dict(data)

    def save_guild(self, cfg: GuildConfig) -> None:
        path = self._guild_path(cfg.guild_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, indent=2)

    def set_admin_if_empty(self, guild_id: int, user_id: int) -> bool:
        cfg = self.load_guild(guild_id)
        if cfg.admin_user_id is None:
            cfg.admin_user_id = user_id
            self.save_guild(cfg)
            return True
        return False

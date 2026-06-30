from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(slots=True)
class Enemy:
    name: str
    hp: int
    defense: int = 12
    atk_bonus: int = 3
    damage: str = "1d6+1"
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Enemy":
        return cls(
            name=str(data.get("name", "Nemico sconosciuto")),
            hp=int(data.get("hp", 10)),
            defense=int(data.get("defense", 12)),
            atk_bonus=int(data.get("atk_bonus", 3)),
            damage=str(data.get("damage", "1d6+1")),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LootItem:
    name: str
    rarity: str = "comune"
    weight: int = 10
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LootItem":
        return cls(
            name=str(data.get("name", "Oggetto misterioso")),
            rarity=str(data.get("rarity", "comune")),
            weight=max(1, int(data.get("weight", 10))),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChannelConfig:
    channel_id: int
    guild_id: int
    title: str
    setting: str
    danger_level: str = "medio"
    ambience_url: str | None = None
    enemies: list[Enemy] = field(default_factory=list)
    loot: list[LootItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelConfig":
        return cls(
            channel_id=int(data["channel_id"]),
            guild_id=int(data["guild_id"]),
            title=str(data.get("title", "Area sconosciuta")),
            setting=str(data.get("setting", "")),
            danger_level=str(data.get("danger_level", "medio")),
            ambience_url=data.get("ambience_url"),
            enemies=[Enemy.from_dict(x) for x in data.get("enemies", [])],
            loot=[LootItem.from_dict(x) for x in data.get("loot", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "title": self.title,
            "setting": self.setting,
            "danger_level": self.danger_level,
            "ambience_url": self.ambience_url,
            "enemies": [e.to_dict() for e in self.enemies],
            "loot": [l.to_dict() for l in self.loot],
        }


@dataclass(slots=True)
class EnemyState:
    name: str
    hp: int
    max_hp: int
    defense: int
    atk_bonus: int
    damage: str
    description: str = ""

    @classmethod
    def from_enemy(cls, enemy: Enemy) -> "EnemyState":
        return cls(
            name=enemy.name,
            hp=enemy.hp,
            max_hp=enemy.hp,
            defense=enemy.defense,
            atk_bonus=enemy.atk_bonus,
            damage=enemy.damage,
            description=enemy.description,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnemyState":
        return cls(
            name=str(data["name"]),
            hp=int(data["hp"]),
            max_hp=int(data.get("max_hp", data["hp"])),
            defense=int(data.get("defense", 12)),
            atk_bonus=int(data.get("atk_bonus", 3)),
            damage=str(data.get("damage", "1d6+1")),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlayerState:
    user_id: int
    name: str
    hp: int = 30
    max_hp: int = 30
    attack_bonus: int = 4
    damage: str = "1d8+2"
    inventory: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerState":
        return cls(
            user_id=int(data["user_id"]),
            name=str(data.get("name", "Giocatore")),
            hp=int(data.get("hp", 30)),
            max_hp=int(data.get("max_hp", 30)),
            attack_bonus=int(data.get("attack_bonus", 4)),
            damage=str(data.get("damage", "1d8+2")),
            inventory=list(data.get("inventory", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CombatState:
    active: bool = False
    round_no: int = 0
    enemies: list[EnemyState] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CombatState":
        return cls(
            active=bool(data.get("active", False)),
            round_no=int(data.get("round_no", 0)),
            enemies=[EnemyState.from_dict(x) for x in data.get("enemies", [])],
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "round_no": self.round_no,
            "enemies": [e.to_dict() for e in self.enemies],
            "notes": self.notes,
        }

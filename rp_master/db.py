from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ChannelConfig, CombatState, PlayerState


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_configs (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS session_state (
                channel_id INTEGER PRIMARY KEY,
                summary TEXT NOT NULL DEFAULT '',
                combat_payload TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self.conn.commit()

    def upsert_channel_config(self, config: ChannelConfig) -> None:
        self.conn.execute(
            """
            INSERT INTO channel_configs (channel_id, guild_id, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                guild_id=excluded.guild_id,
                payload=excluded.payload
            """,
            (config.channel_id, config.guild_id, json.dumps(config.to_dict(), ensure_ascii=False)),
        )
        self.conn.commit()

    def get_channel_config(self, channel_id: int) -> ChannelConfig | None:
        row = self.conn.execute(
            "SELECT payload FROM channel_configs WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        if not row:
            return None
        return ChannelConfig.from_dict(json.loads(row["payload"]))

    def set_summary(self, channel_id: int, summary: str) -> None:
        self.conn.execute(
            """
            INSERT INTO session_state (channel_id, summary, combat_payload)
            VALUES (?, ?, '{}')
            ON CONFLICT(channel_id) DO UPDATE SET summary=excluded.summary
            """,
            (channel_id, summary),
        )
        self.conn.commit()

    def get_summary(self, channel_id: int) -> str:
        row = self.conn.execute(
            "SELECT summary FROM session_state WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        return row["summary"] if row else ""

    def set_combat(self, channel_id: int, combat: CombatState) -> None:
        self.conn.execute(
            """
            INSERT INTO session_state (channel_id, summary, combat_payload)
            VALUES (?, '', ?)
            ON CONFLICT(channel_id) DO UPDATE SET combat_payload=excluded.combat_payload
            """,
            (channel_id, json.dumps(combat.to_dict(), ensure_ascii=False)),
        )
        self.conn.commit()

    def get_combat(self, channel_id: int) -> CombatState:
        row = self.conn.execute(
            "SELECT combat_payload FROM session_state WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        if not row:
            return CombatState()
        return CombatState.from_dict(json.loads(row["combat_payload"]))

    def upsert_player(self, guild_id: int, player: PlayerState) -> None:
        self.conn.execute(
            """
            INSERT INTO players (guild_id, user_id, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET payload=excluded.payload
            """,
            (guild_id, player.user_id, json.dumps(player.to_dict(), ensure_ascii=False)),
        )
        self.conn.commit()

    def get_player(self, guild_id: int, user_id: int, fallback_name: str) -> PlayerState:
        row = self.conn.execute(
            "SELECT payload FROM players WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if not row:
            player = PlayerState(user_id=user_id, name=fallback_name)
            self.upsert_player(guild_id, player)
            return player
        data = json.loads(row["payload"])
        if not data.get("name"):
            data["name"] = fallback_name
        return PlayerState.from_dict(data)

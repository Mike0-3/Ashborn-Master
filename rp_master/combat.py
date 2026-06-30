from __future__ import annotations

import random
import re
from typing import Any

from .models import ChannelConfig, CombatState, EnemyState, PlayerState

DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def roll_dice(expr: str) -> tuple[int, list[int], int]:
    m = DICE_RE.match(expr.replace(" ", ""))
    if not m:
        raise ValueError(f"Formula dadi non valida: {expr}")
    n = int(m.group(1))
    faces = int(m.group(2))
    mod = int(m.group(3) or 0)
    rolls = [random.randint(1, faces) for _ in range(n)]
    return sum(rolls) + mod, rolls, mod


def start_combat(config: ChannelConfig) -> CombatState:
    if not config.enemies:
        return CombatState(active=False, round_no=0, enemies=[], notes="Nessun nemico configurato.")
    enemy_pool = [EnemyState.from_enemy(e) for e in config.enemies]
    count = min(len(enemy_pool), random.randint(1, min(3, len(enemy_pool))))
    selected = random.sample(enemy_pool, k=count)
    return CombatState(active=True, round_no=1, enemies=selected, notes=f"Scontro in {config.title}")


def choose_target(combat: CombatState, target_name: str | None) -> EnemyState | None:
    living = [e for e in combat.enemies if e.hp > 0]
    if not living:
        return None
    if not target_name:
        return living[0]
    target_name = target_name.lower().strip()
    for enemy in living:
        if target_name in enemy.name.lower():
            return enemy
    return living[0]


def player_attack(player: PlayerState, combat: CombatState, target_name: str | None, flavor_action: str | None = None) -> dict[str, Any]:
    target = choose_target(combat, target_name)
    if target is None:
        combat.active = False
        return {
            "hit": False,
            "ended": True,
            "text": "Non ci sono più nemici da colpire.",
            "combat": combat,
        }

    d20 = random.randint(1, 20)
    total = d20 + player.attack_bonus
    crit = d20 == 20
    hit = crit or total >= target.defense
    damage_total = 0
    damage_rolls: list[int] = []
    damage_mod = 0
    if hit:
        damage_total, damage_rolls, damage_mod = roll_dice(player.damage)
        if crit:
            damage_total *= 2
        target.hp = max(0, target.hp - damage_total)

    text = (
        f"{player.name} tenta: **{flavor_action or 'attacco'}**. "
        f"Tiro colpire: **{d20} + {player.attack_bonus} = {total}** contro DIF **{target.defense}**. "
    )
    if hit:
        text += f"Colpo a segno su **{target.name}** per **{damage_total}** danni"
        if damage_rolls:
            text += f" (tiri {damage_rolls}, mod {damage_mod})"
        if crit:
            text += " — **colpo critico!**"
        text += "."
        if target.hp <= 0:
            text += f" **{target.name}** viene sconfitto."
    else:
        text += f"Mancato su **{target.name}**."

    if all(enemy.hp <= 0 for enemy in combat.enemies):
        combat.active = False
        text += "\n\n🏁 Tutti i nemici sono stati eliminati."

    return {
        "hit": hit,
        "crit": crit,
        "target": target.name,
        "damage": damage_total,
        "text": text,
        "combat": combat,
    }


def enemy_round(player: PlayerState, combat: CombatState) -> dict[str, Any]:
    if not combat.active:
        return {"text": "", "player": player, "combat": combat, "downed": False}

    lines: list[str] = []
    downed = False
    for enemy in [e for e in combat.enemies if e.hp > 0]:
        d20 = random.randint(1, 20)
        total = d20 + enemy.atk_bonus
        armor = 12
        if total >= armor:
            dmg, rolls, mod = roll_dice(enemy.damage)
            player.hp = max(0, player.hp - dmg)
            lines.append(
                f"**{enemy.name}** colpisce **{player.name}**: {d20}+{enemy.atk_bonus}={total}, danni **{dmg}** (tiri {rolls}, mod {mod})."
            )
            if player.hp <= 0:
                downed = True
                lines.append(f"💥 **{player.name}** è a terra.")
                break
        else:
            lines.append(f"**{enemy.name}** manca **{player.name}**: {d20}+{enemy.atk_bonus}={total}.")

    return {
        "text": "\n".join(lines),
        "player": player,
        "combat": combat,
        "downed": downed,
    }

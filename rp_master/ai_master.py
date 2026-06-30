from __future__ import annotations

from textwrap import shorten
from openai import AsyncOpenAI

from .models import ChannelConfig, CombatState, PlayerState
from .prompts import MASTER_SYSTEM_PROMPT


class AIMaster:
    def __init__(self, api_key: str | None, base_url: str, model: str):
        self.model = model
        self.enabled = bool(api_key)
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key else None

    async def narrate(
        self,
        *,
        config: ChannelConfig,
        player: PlayerState,
        summary: str,
        prompt: str,
        combat: CombatState | None = None,
        mechanical_result: str | None = None,
    ) -> str:
        if not self.enabled or self.client is None:
            base = [
                f"**{config.title}** — {config.setting}",
                f"Pericolo percepito: **{config.danger_level}**.",
                f"{player.name} osserva la scena.",
            ]
            if mechanical_result:
                base.append(mechanical_result)
            base.append(f"Input del giocatore: {prompt}")
            if summary:
                base.append(f"Riassunto sessione: {shorten(summary, width=450, placeholder='...')}")
            return "\n\n".join(base)

        combat_text = "Nessun combattimento attivo."
        if combat and combat.active:
            enemy_lines = [f"- {e.name}: {e.hp}/{e.max_hp} HP, DIF {e.defense}, danno {e.damage}" for e in combat.enemies]
            combat_text = "Combattimento attivo:\n" + "\n".join(enemy_lines)

        user_prompt = f"""
Canale: {config.title}
Ambientazione: {config.setting}
Livello pericolo: {config.danger_level}
Nemici possibili: {', '.join(e.name for e in config.enemies) or 'nessuno'}
Loot possibile: {', '.join(l.name for l in config.loot) or 'nessuno'}
Giocatore attivo: {player.name} (HP {player.hp}/{player.max_hp})
Riassunto recente: {summary or 'nessun evento rilevante memorizzato'}
{combat_text}
Risultato meccanico già deciso: {mechanical_result or 'nessuno'}
Richiesta / azione del giocatore: {prompt}

Scrivi una risposta da Game Master in 1-3 paragrafi, concreta e adatta a Discord.
""".strip()

        response = await self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
            max_output_tokens=350,
        )
        return (response.output_text or "Il Master resta in silenzio per un istante.").strip()

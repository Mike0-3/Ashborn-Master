from __future__ import annotations

import json
import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from rp_master.ai_master import AIMaster
from rp_master.combat import enemy_round, player_attack, start_combat
from rp_master.config import load_settings
from rp_master.db import Database
from rp_master.loot import draw_loot
from rp_master.models import ChannelConfig, CombatState, Enemy, LootItem
from rp_master.music import MusicController

logging.basicConfig(level=logging.INFO)
settings = load_settings()

if not settings.discord_token:
    raise RuntimeError("DISCORD_TOKEN mancante nel file .env")

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = False
intents.message_content = settings.enable_message_content

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database(settings.database_path)
ai_master = AIMaster(settings.ai_api_key, settings.ai_base_url, settings.ai_model)
music = MusicController(settings.ffmpeg_path)

rp_group = app_commands.Group(name="rp", description="Comandi del Master roleplay")
admin_group = app_commands.Group(name="rpadmin", description="Configurazione admin per il Master")


def _truncate(text: str, limit: int = 1800) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _ensure_guild(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        raise app_commands.AppCommandError("Questo comando può essere usato solo in un server.")


def _get_channel_config_or_raise(channel_id: int) -> ChannelConfig:
    config = db.get_channel_config(channel_id)
    if not config:
        raise app_commands.AppCommandError(
            "Questo canale RP non è configurato. Usa /rpadmin set_area per inizializzarlo."
        )
    return config


def _parse_enemies(raw: str) -> list[Enemy]:
    enemies: list[Enemy] = []
    for part in [x.strip() for x in raw.split(";") if x.strip()]:
        fields = [x.strip() for x in part.split("|")]
        name = fields[0]
        hp = int(fields[1]) if len(fields) > 1 and fields[1] else 10
        defense = int(fields[2]) if len(fields) > 2 and fields[2] else 12
        atk_bonus = int(fields[3]) if len(fields) > 3 and fields[3] else 3
        damage = fields[4] if len(fields) > 4 and fields[4] else "1d6+1"
        description = fields[5] if len(fields) > 5 else ""
        enemies.append(Enemy(name=name, hp=hp, defense=defense, atk_bonus=atk_bonus, damage=damage, description=description))
    return enemies


def _parse_loot(raw: str) -> list[LootItem]:
    loot: list[LootItem] = []
    for part in [x.strip() for x in raw.split(";") if x.strip()]:
        fields = [x.strip() for x in part.split("|")]
        name = fields[0]
        rarity = fields[1] if len(fields) > 1 and fields[1] else "comune"
        weight = int(fields[2]) if len(fields) > 2 and fields[2] else 10
        description = fields[3] if len(fields) > 3 else ""
        loot.append(LootItem(name=name, rarity=rarity, weight=weight, description=description))
    return loot


async def _narrate_and_send(
    interaction: discord.Interaction,
    *,
    prompt: str,
    mechanical_result: str | None = None,
) -> None:
    _ensure_guild(interaction)
    config = _get_channel_config_or_raise(interaction.channel_id)
    player = db.get_player(interaction.guild_id, interaction.user.id, interaction.user.display_name)
    summary = db.get_summary(interaction.channel_id)
    combat = db.get_combat(interaction.channel_id)
    narration = await ai_master.narrate(
        config=config,
        player=player,
        summary=summary,
        prompt=prompt,
        combat=combat,
        mechanical_result=mechanical_result,
    )
    new_summary = " | ".join(filter(None, [summary[-900:], prompt, mechanical_result or "", narration]))[-1800:]
    db.set_summary(interaction.channel_id, new_summary)
    await interaction.followup.send(_truncate(narration))


@bot.event
async def on_ready() -> None:
    logging.info("Bot online come %s", bot.user)
    if settings.channel_bootstrap_file and Path(settings.channel_bootstrap_file).exists():
        data = json.loads(Path(settings.channel_bootstrap_file).read_text(encoding="utf-8"))
        for item in data.get("channels", []):
            config = ChannelConfig.from_dict(item)
            db.upsert_channel_config(config)
        logging.info("Bootstrap canali caricato da %s", settings.channel_bootstrap_file)

    if settings.app_guild_id:
        guild_obj = discord.Object(id=settings.app_guild_id)
        bot.tree.copy_global_to(guild=guild_obj)
        await bot.tree.sync(guild=guild_obj)
        logging.info("Slash commands sincronizzati sulla guild di test %s", settings.app_guild_id)
    else:
        await bot.tree.sync()
        logging.info("Slash commands globali sincronizzati")


@rp_group.command(name="summon", description="Richiama il Master per descrivere la scena")
async def rp_summon(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await _narrate_and_send(interaction, prompt="Descrivi l'area circostante e i dettagli immediatamente percepibili.")


@rp_group.command(name="action", description="Esegui un'azione narrativa")
@app_commands.describe(testo="Cosa fa il personaggio")
async def rp_action(interaction: discord.Interaction, testo: str):
    await interaction.response.defer(thinking=True)
    await _narrate_and_send(interaction, prompt=f"Azione del personaggio: {testo}")


@rp_group.command(name="combat_start", description="Avvia uno scontro nel canale corrente")
async def rp_combat_start(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    config = _get_channel_config_or_raise(interaction.channel_id)
    combat = start_combat(config)
    db.set_combat(interaction.channel_id, combat)
    if not combat.active:
        await interaction.followup.send("Nessun nemico configurato per questo canale.")
        return
    enemies = "\n".join(f"- **{e.name}** ({e.hp}/{e.max_hp} HP, DIF {e.defense}, danno {e.damage})" for e in combat.enemies)
    mechanical = f"Combattimento avviato. Round {combat.round_no}. Nemici:\n{enemies}"
    await _narrate_and_send(interaction, prompt="Introduce l'inizio dello scontro e la minaccia imminente.", mechanical_result=mechanical)


@rp_group.command(name="attack", description="Attacca un nemico durante il combattimento")
@app_commands.describe(target="Nome o parte del nome del bersaglio", azione="Descrizione narrativa dell'attacco")
async def rp_attack(interaction: discord.Interaction, target: str | None = None, azione: str | None = None):
    await interaction.response.defer(thinking=True)
    _ensure_guild(interaction)
    combat = db.get_combat(interaction.channel_id)
    if not combat.active:
        await interaction.followup.send("Non c'è alcun combattimento attivo in questo canale.")
        return
    player = db.get_player(interaction.guild_id, interaction.user.id, interaction.user.display_name)
    result = player_attack(player, combat, target, azione)
    if combat.active:
        combat.round_no += 1
    retaliation = enemy_round(player, combat)
    db.upsert_player(interaction.guild_id, player)
    db.set_combat(interaction.channel_id, combat)
    mechanical = result["text"]
    if retaliation["text"]:
        mechanical += "\n" + retaliation["text"]
    if retaliation["downed"]:
        mechanical += f"\n❤️ Stato di {player.name}: {player.hp}/{player.max_hp} HP."
    await _narrate_and_send(
        interaction,
        prompt=f"Risolvi narrativamente l'attacco di {player.name} e la risposta dei nemici.",
        mechanical_result=mechanical,
    )


@rp_group.command(name="status", description="Mostra stato del personaggio e del combattimento")
async def rp_status(interaction: discord.Interaction):
    _ensure_guild(interaction)
    player = db.get_player(interaction.guild_id, interaction.user.id, interaction.user.display_name)
    combat = db.get_combat(interaction.channel_id)
    lines = [
        f"**{player.name}** — HP {player.hp}/{player.max_hp}",
        f"Bonus attacco: {player.attack_bonus}",
        f"Danno: {player.damage}",
        f"Inventario: {', '.join(player.inventory) if player.inventory else 'vuoto'}",
    ]
    if combat.active:
        lines.append(f"\n**Combattimento attivo — round {combat.round_no}**")
        for enemy in combat.enemies:
            lines.append(f"- {enemy.name}: {enemy.hp}/{enemy.max_hp} HP")
    else:
        lines.append("\nNessun combattimento attivo.")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@rp_group.command(name="loot_spin", description="Estrae loot casuale del canale")
async def rp_loot_spin(interaction: discord.Interaction):
    _ensure_guild(interaction)
    config = _get_channel_config_or_raise(interaction.channel_id)
    loot = draw_loot(config.loot)
    if loot is None:
        await interaction.response.send_message("Non c'è alcun loot configurato per quest'area.")
        return
    player = db.get_player(interaction.guild_id, interaction.user.id, interaction.user.display_name)
    player.inventory.append(loot.name)
    db.upsert_player(interaction.guild_id, player)
    text = (
        f"🎁 **{player.name}** trova: **{loot.name}**\n"
        f"Rarità: **{loot.rarity}**\n"
        f"Dettagli: {loot.description or 'Nessuna descrizione.'}"
    )
    await interaction.response.send_message(text)


@rp_group.command(name="music_here", description="Entra in vocale e avvia l'ambience del canale")
async def rp_music_here(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    config = _get_channel_config_or_raise(interaction.channel_id)
    if not config.ambience_url:
        await interaction.followup.send("Questo canale non ha un ambience_url configurato.", ephemeral=True)
        return
    msg = await music.play(interaction, config.ambience_url)
    await interaction.followup.send(msg, ephemeral=True)


@rp_group.command(name="music_stop", description="Ferma la musica e lascia la vocale")
async def rp_music_stop(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    msg = await music.stop(interaction)
    await interaction.followup.send(msg, ephemeral=True)


@admin_group.command(name="set_area", description="Configura l'ambientazione del canale attuale")
@app_commands.describe(
    titolo="Nome dell'area",
    ambientazione="Descrizione dell'ambientazione del canale",
    pericolo="Basso, medio, alto, estremo...",
    enemies="Formato: Nome|HP|DIF|ATK|DMG|descr; Nome2|...",
    loot="Formato: Nome|rarità|peso|descr; Nome2|...",
    ambience_url="URL audio diretto o path locale sul server",
)
async def rpadmin_set_area(
    interaction: discord.Interaction,
    titolo: str,
    ambientazione: str,
    pericolo: str,
    enemies: str,
    loot: str,
    ambience_url: str | None = None,
):
    _ensure_guild(interaction)
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("Ti serve il permesso Gestisci Canali.", ephemeral=True)
        return
    config = ChannelConfig(
        channel_id=interaction.channel_id,
        guild_id=interaction.guild_id,
        title=titolo,
        setting=ambientazione,
        danger_level=pericolo,
        ambience_url=ambience_url,
        enemies=_parse_enemies(enemies),
        loot=_parse_loot(loot),
    )
    db.upsert_channel_config(config)
    await interaction.response.send_message(
        f"✅ Area configurata per **{titolo}** con {len(config.enemies)} nemici e {len(config.loot)} voci loot.",
        ephemeral=True,
    )


@admin_group.command(name="reset_session", description="Azzera memoria narrativa e combattimento del canale")
async def rpadmin_reset_session(interaction: discord.Interaction):
    _ensure_guild(interaction)
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("Ti serve il permesso Gestisci Canali.", ephemeral=True)
        return
    db.set_summary(interaction.channel_id, "")
    db.set_combat(interaction.channel_id, CombatState())
    await interaction.response.send_message("♻️ Sessione del canale resettata.", ephemeral=True)


@admin_group.command(name="show_config", description="Mostra la configurazione del canale")
async def rpadmin_show_config(interaction: discord.Interaction):
    _ensure_guild(interaction)
    config = _get_channel_config_or_raise(interaction.channel_id)
    payload = json.dumps(config.to_dict(), ensure_ascii=False, indent=2)
    await interaction.response.send_message(f"```json\n{_truncate(payload, 1800)}\n```", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    message = str(error) or "Si è verificato un errore durante l'esecuzione del comando."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception:
        logging.exception("Errore non gestito nei comandi", exc_info=error)


bot.tree.add_command(rp_group)
bot.tree.add_command(admin_group)


if __name__ == "__main__":
    bot.run(settings.discord_token)

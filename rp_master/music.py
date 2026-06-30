from __future__ import annotations

from pathlib import Path
import discord


class MusicController:
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    async def join_author_channel(self, interaction: discord.Interaction) -> discord.VoiceClient:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            raise RuntimeError("Utente non valido.")
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            raise RuntimeError("Devi essere in una vocale per richiamare la musica del Master.")

        target_channel = interaction.user.voice.channel
        existing = interaction.guild.voice_client if interaction.guild else None
        if existing and existing.channel.id != target_channel.id:
            await existing.move_to(target_channel)
            return existing
        if existing:
            return existing
        return await target_channel.connect()

    def _make_source(self, source: str) -> discord.AudioSource:
        before = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        if Path(source).exists():
            return discord.FFmpegPCMAudio(source, executable=self.ffmpeg_path)
        return discord.FFmpegPCMAudio(source, executable=self.ffmpeg_path, before_options=before)

    async def play(self, interaction: discord.Interaction, source: str) -> str:
        vc = await self.join_author_channel(interaction)
        if vc.is_playing():
            vc.stop()
        audio = self._make_source(source)
        vc.play(audio)
        return f"🎵 Ambience avviata in **{vc.channel.name}**."

    async def stop(self, interaction: discord.Interaction) -> str:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc:
            return "Nessuna riproduzione attiva."
        if vc.is_playing():
            vc.stop()
        await vc.disconnect(force=True)
        return "⏹️ Musica fermata e bot uscito dalla vocale."

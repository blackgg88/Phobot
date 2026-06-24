from __future__ import annotations

import discord

BOT_CHANNEL_NAME = "🚀│phobot"


def get_bot_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Devuelve el canal del bot en el servidor, o None si no existe."""
    ch = discord.utils.get(guild.text_channels, name=BOT_CHANNEL_NAME)
    if ch and ch.permissions_for(guild.me).send_messages:
        return ch
    return None

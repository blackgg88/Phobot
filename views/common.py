from __future__ import annotations
import discord


async def ack(interaction: discord.Interaction) -> None:
    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except Exception:
        pass


async def edit_interaction_message(interaction: discord.Interaction, **kwargs) -> None:
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)
    except Exception:
        try:
            await interaction.message.edit(**kwargs)
        except Exception:
            pass

from __future__ import annotations

import asyncio
import os

import discord
from discord.ext import commands

from config import BOT_TOKEN

COGS = [
    "cogs.help_cog",
    "cogs.economy_cog",
    "cogs.gacha_cog",
    "cogs.collection_cog",
    "cogs.wishlist_cog",
    "cogs.casino_cog",
    "cogs.museum_cog",
    "cogs.inventory_cog",
    "cogs.buy_cog",
    "cogs.trade_cog",
    "cogs.tokens_cog",
    "cogs.admin_cog",
]


async def main() -> None:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members          = True

    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or("!"),
        intents=intents,
        help_command=None,
        case_insensitive=True,
    )

    @bot.event
    async def on_ready() -> None:
        print(f"[READY] Bot listo: {bot.user} ({bot.user.id})")

    @bot.event
    async def on_message(message: discord.Message) -> None:
        print(f"[MSG] {message.author}: {message.content}")
        await bot.process_commands(message)

    @bot.event
    async def on_command_error(ctx: commands.Context, error) -> None:
        print(f"[CMD ERROR] {type(error).__name__}: {error}")
        if isinstance(error, commands.CommandNotFound):
            await ctx.reply(f"Comando no encontrado: `{ctx.invoked_with}`")
            return
        if isinstance(error, commands.CheckFailure):
            try:
                await ctx.reply("No tenés permisos para ese comando.")
            except Exception:
                pass
            return
        raise error

    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  [OK] {cog}")
        except Exception as e:
            print(f"  [ERROR] {cog}: {e}")

    await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

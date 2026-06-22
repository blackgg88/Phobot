from __future__ import annotations

import discord
from discord.ext import commands

from core.cards import migrate_users_cards, normalize_cards
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from views.trade import ACTIVE_TRADE_USERS, TradeSession, TradeInviteView, _next_trade_id


class TradeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ptrade")
    async def ptrade_cmd(self, ctx: commands.Context, target: discord.Member = None) -> None:
        if not target:
            await ctx.reply("Uso: `ptrade @usuario`")
            return
        if target.bot:
            await ctx.reply("No podés intercambiar con un bot.")
            return
        if target.id == ctx.author.id:
            await ctx.reply("No podés intercambiar contigo mismo.")
            return

        if ctx.author.id in ACTIVE_TRADE_USERS:
            await ctx.reply("Ya tenés un intercambio activo. Cancelalo primero.")
            return
        if target.id in ACTIVE_TRADE_USERS:
            await ctx.reply(f"{target.display_name} ya tiene un intercambio activo.")
            return

        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, str(ctx.author.id))
        ensure_user(users, str(target.id))

        session = TradeSession(
            trade_id  = _next_trade_id(),
            a_user_id = ctx.author.id,
            b_user_id = target.id,
        )

        view = TradeInviteView(session=session)
        e = discord.Embed(
            title="🔄 Invitación de intercambio",
            description=f"{ctx.author.mention} quiere intercambiar cartas con vos, {target.mention}.\n¿Aceptás?",
            color=0x3498db,
        )
        await ctx.send(target.mention, embed=e, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TradeCog(bot))

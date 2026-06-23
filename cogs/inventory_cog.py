from __future__ import annotations

import discord
from discord.ext import commands

from core.cards import migrate_users_cards, normalize_cards
from core.storage import get_paths, load_json
from core.users import ensure_user, pick_target_member, save_users
from views.inventory import InventoryView


class InventoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="pinv")
    async def pinv_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target  = pick_target_member(ctx, member) or ctx.author
        uid     = str(target.id)

        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, uid)

        view  = InventoryView(viewer_id=ctx.author.id, target_user_id=uid)
        embed = view.make_embed(users, cards_db)
        await ctx.reply(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InventoryCog(bot))

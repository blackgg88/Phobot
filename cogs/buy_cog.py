from __future__ import annotations

from discord.ext import commands

from core.storage import get_paths, load_json
from core.users import ensure_user
from views.packs import PacksOpenView
from views.store import StoreView


class BuyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ptienda")
    async def ptienda_cmd(self, ctx: commands.Context) -> None:
        view  = StoreView(user_id=ctx.author.id)
        embed = view.make_embed()
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="psobres")
    async def psobres_cmd(self, ctx: commands.Context) -> None:
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(ctx.author.id)
        ensure_user(users, uid)
        packs = users[uid].get("packs", {})
        has   = any(packs.get(r, 0) > 0 for r in ["common", "rare", "epic", "legendary", "mythic"])
        if not has:
            await ctx.reply("No tenés sobres. Conseguilos en eventos o como recompensas.")
            return
        view  = PacksOpenView(viewer_id=ctx.author.id)
        embed = view.make_embed()
        await ctx.reply(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BuyCog(bot))

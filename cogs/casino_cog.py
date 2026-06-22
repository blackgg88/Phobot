from __future__ import annotations

from discord.ext import commands

from core.storage import get_paths, load_json
from core.users import ensure_user
from views.casino import CasinoLobbyView


class CasinoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="pcasino")
    async def pcasino_cmd(self, ctx: commands.Context) -> None:
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(ctx.author.id)
        ensure_user(users, uid)
        gold = int(users[uid].get("gold", 0))

        view  = CasinoLobbyView(user_id=ctx.author.id, gold=gold)
        embed = view.make_embed()
        await ctx.reply(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CasinoCog(bot))

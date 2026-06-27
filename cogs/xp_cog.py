from __future__ import annotations

from discord.ext import commands

from core.levels import try_add_xp, level_from_xp
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users


class XpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        if ctx.author.bot:
            return

        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(ctx.author.id)
        ensure_user(users, uid)

        gained, leveled_up = try_add_xp(users, uid)
        if gained:
            save_users(users)
            if leveled_up:
                new_level = level_from_xp(users[uid]["xp"])
                try:
                    await ctx.send(
                        f"🎉 {ctx.author.mention} subió al **nivel {new_level}**!",
                        delete_after=15,
                    )
                except Exception:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(XpCog(bot))

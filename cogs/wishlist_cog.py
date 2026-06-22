from __future__ import annotations

import discord
from discord.ext import commands

from core.storage import get_paths, load_json
from core.users import ensure_user, normalize_wish, save_users


class WishlistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load_users(self):
        users_path, _, _ = get_paths()
        return load_json(users_path, {})

    @commands.command(name="pwl")
    async def pwl_cmd(self, ctx: commands.Context) -> None:
        users = self._load_users()
        uid   = str(ctx.author.id)
        ensure_user(users, uid)
        wl    = users[uid].get("wishlist", [])
        if not wl:
            await ctx.reply("Tu wishlist está vacía. Usá `pwladd <carta>` para agregar.")
            return
        lines = "\n".join(f"• {w}" for w in wl)
        e = discord.Embed(title="⭐ Tu Wishlist", description=lines, color=0xf39c12)
        await ctx.reply(embed=e)

    @commands.command(name="pwladd")
    async def pwladd_cmd(self, ctx: commands.Context, *, name: str = "") -> None:
        if not name:
            await ctx.reply("Uso: `pwladd <nombre de carta>`")
            return
        users = self._load_users()
        uid   = str(ctx.author.id)
        ensure_user(users, uid)
        norm = normalize_wish(name)
        wl   = users[uid].setdefault("wishlist", [])
        if any(normalize_wish(w) == norm for w in wl):
            await ctx.reply("Esa carta ya está en tu wishlist.")
            return
        if len(wl) >= 20:
            await ctx.reply("Tu wishlist tiene el máximo de 20 cartas.")
            return
        wl.append(name.strip())
        save_users(users)
        await ctx.reply(f"✅ Agregado **{name.strip()}** a tu wishlist.")

    @commands.command(name="pwlremove")
    async def pwlremove_cmd(self, ctx: commands.Context, *, name: str = "") -> None:
        if not name:
            await ctx.reply("Uso: `pwlremove <nombre de carta>`")
            return
        users = self._load_users()
        uid   = str(ctx.author.id)
        ensure_user(users, uid)
        norm = normalize_wish(name)
        wl   = users[uid].get("wishlist", [])
        match = next((w for w in wl if normalize_wish(w) == norm), None)
        if not match:
            await ctx.reply("Esa carta no está en tu wishlist.")
            return
        wl.remove(match)
        save_users(users)
        await ctx.reply(f"✅ Quitado **{match}** de tu wishlist.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WishlistCog(bot))

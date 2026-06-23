from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from core.cards import find_card_matches, normalize_cards
from core.storage import get_paths, load_json
from core.users import ensure_user, normalize_wish, save_users


class WishlistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        return users, cards_db

    @commands.command(name="pwl")
    async def pwl_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid      = str(ctx.author.id)
        ensure_user(users, uid)
        wl = users[uid].get("wishlist", [])
        if not wl:
            await ctx.reply("Tu wishlist está vacía. Usá `!pwladd <carta>` para agregar.")
            return
        lines = "\n".join(f"• {w}" for w in wl)
        e = discord.Embed(title="⭐ Tu Wishlist", description=lines, color=0xf39c12)
        await ctx.reply(embed=e)

    @commands.command(name="pwladd")
    async def pwladd_cmd(self, ctx: commands.Context, *, name: str = "") -> None:
        if not name:
            await ctx.reply("Uso: `!pwladd <nombre de carta>`")
            return

        users, cards_db = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)

        matches = find_card_matches(cards_db, name)

        if not matches:
            await ctx.reply(f"❌ No existe ninguna carta llamada **{name.strip()}**.")
            return

        # si hay varios personajes con ese nombre, preguntar cuál
        if len(matches) > 1:
            lines = "\n".join(
                f"`{i}.` **{n}** — *{c}*" for i, (n, c) in enumerate(matches, 1)
            )
            e = discord.Embed(
                title=f"¿Cuál **{name.strip()}** querés agregar?",
                description=lines,
                color=0x3498db,
            )
            e.set_footer(text="Respondé con el número (timeout: 30s)")
            await ctx.reply(embed=e)

            def check(m):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Se venció el tiempo.")
                return

            raw = msg.content.strip()
            if not raw.isdigit() or not (1 <= int(raw) <= len(matches)):
                await ctx.send("Número inválido, cancelado.")
                return

            chosen_name, chosen_col = matches[int(raw) - 1]
        else:
            chosen_name, chosen_col = matches[0]

        wl = users[uid].setdefault("wishlist", [])

        if any(normalize_wish(w) == normalize_wish(chosen_name) for w in wl):
            await ctx.reply("Esa carta ya está en tu wishlist.")
            return
        if len(wl) >= 20:
            await ctx.reply("Tu wishlist tiene el máximo de 20 cartas.")
            return

        entry = f"{chosen_name} • {chosen_col}"
        wl.append(entry)
        save_users(users)
        await ctx.reply(f"✅ Agregado **{chosen_name}** (*{chosen_col}*) a tu wishlist.")

    @commands.command(name="pwlremove")
    async def pwlremove_cmd(self, ctx: commands.Context, *, name: str = "") -> None:
        if not name:
            await ctx.reply("Uso: `!pwlremove <nombre de carta>`")
            return
        users, _ = self._load()
        uid  = str(ctx.author.id)
        ensure_user(users, uid)
        norm = normalize_wish(name)
        wl   = users[uid].get("wishlist", [])
        # entradas nuevas tienen formato "Nombre • Serie", las viejas solo "Nombre"
        match = next(
            (w for w in wl if normalize_wish(w.split("•")[0]) == norm), None
        )
        if not match:
            await ctx.reply("Esa carta no está en tu wishlist.")
            return
        wl.remove(match)
        save_users(users)
        await ctx.reply(f"✅ Quitado **{match}** de tu wishlist.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WishlistCog(bot))

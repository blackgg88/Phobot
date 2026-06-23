from __future__ import annotations

import discord
from discord.ext import commands

from config import MUSEUM_BACKGROUNDS
from core.cards import find_instance_by_code, migrate_users_cards, normalize_cards
from core.frames import load_frames_catalog
from core.storage import get_paths, load_json
from core.users import ensure_user, pick_target_member, save_users
from rendering.cards import pil_to_discord_file
from rendering.museum import build_museum_image


class MuseumCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    @commands.command(name="pmuseo")
    async def pmuseo_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target  = pick_target_member(ctx, member) or ctx.author
        users, cards_db = self._load()
        uid     = str(target.id)
        ensure_user(users, uid)

        museum   = users[uid].get("museum", [None] * 10)
        bg_key   = users[uid].get("museum_bg", "negro")
        inst_list = []
        for slot_code in museum:
            if slot_code is None:
                inst_list.append(None)
            else:
                inst = find_instance_by_code(users[uid].get("cards", []), str(slot_code).lower())
                inst_list.append(inst)

        img = build_museum_image(cards_db, inst_list, bg_key=bg_key)
        f   = pil_to_discord_file(img, "museo.png")
        e   = discord.Embed(
            title=f"🏛️ Museo de {target.display_name}",
            color=0x2c3e50,
        ).set_image(url="attachment://museo.png")
        await ctx.reply(embed=e, file=f)

    @commands.command(name="pmadd")
    async def pmadd_cmd(self, ctx: commands.Context, code: str = "", slot: str = "") -> None:
        if not code or not slot:
            await ctx.reply("Uso: `pmadd <código> <slot 1-10>`")
            return
        try:
            slot_idx = int(slot) - 1
            assert 0 <= slot_idx <= 9
        except Exception:
            await ctx.reply("El slot debe ser un número entre 1 y 10.")
            return

        users, cards_db = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        inst = find_instance_by_code(users[uid].get("cards", []), code.strip().lower())
        if not inst:
            await ctx.reply(f"No encontré la carta `{code}` en tu inventario.")
            return

        museum = users[uid].setdefault("museum", [None] * 10)
        while len(museum) < 10:
            museum.append(None)

        museum[slot_idx] = inst.get("code")
        save_users(users)
        await ctx.reply(f"✅ `{inst.get('name')}` puesto en el slot **{slot_idx + 1}** del museo.")

    @commands.command(name="pmremove")
    async def pmremove_cmd(self, ctx: commands.Context, slot: str = "") -> None:
        if not slot:
            await ctx.reply("Uso: `pmremove <slot 1-10>`")
            return
        try:
            slot_idx = int(slot) - 1
            assert 0 <= slot_idx <= 9
        except Exception:
            await ctx.reply("El slot debe ser entre 1 y 10.")
            return

        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        museum = users[uid].setdefault("museum", [None] * 10)
        while len(museum) < 10:
            museum.append(None)
        museum[slot_idx] = None
        save_users(users)
        await ctx.reply(f"✅ Slot **{slot_idx + 1}** del museo vaciado.")

    @commands.command(name="pmclear")
    async def pmclear_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        users[uid]["museum"] = [None] * 10
        save_users(users)
        await ctx.reply("✅ Museo limpiado.")

    @commands.command(name="pmset")
    async def pmset_cmd(self, ctx: commands.Context, *, bg: str = "") -> None:
        bg = bg.strip().lower()
        if bg not in MUSEUM_BACKGROUNDS:
            opts = ", ".join(MUSEUM_BACKGROUNDS.keys())
            await ctx.reply(f"Fondo inválido. Opciones: {opts}")
            return
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        users[uid]["museum_bg"] = bg
        save_users(users)
        await ctx.reply(f"✅ Fondo del museo cambiado a **{bg}**.")

    @commands.command(name="pmarcos")
    async def pmarcos_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target = await pick_target_member(ctx, member) or ctx.author
        users, _ = self._load()
        uid = str(target.id)
        ensure_user(users, uid)

        owned_frame_ids = users[uid].get("frames", [])
        catalog         = load_frames_catalog()
        if not owned_frame_ids:
            await ctx.reply(f"{target.display_name} no tiene marcos.")
            return

        lines = []
        for fid in owned_frame_ids:
            meta = catalog.get(fid) or catalog.get(int(fid))
            name = (meta or {}).get("name", "?")
            lines.append(f"• ID **{fid}** — {name}")

        e = discord.Embed(
            title=f"🖼️ Marcos de {target.display_name}",
            description="\n".join(lines),
            color=0x9b59b6,
        )
        await ctx.reply(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MuseumCog(bot))

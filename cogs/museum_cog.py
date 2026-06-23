from __future__ import annotations

import discord
from discord.ext import commands

from config import MUSEUM_BACKGROUNDS
from core.cards import find_instance_by_code, migrate_users_cards, normalize_cards
from core.frames import load_frames_catalog
from core.museum_bgs import get_user_owned_bgs, load_museum_bg_catalog
from core.storage import get_paths, load_json
from core.users import ensure_user, pick_target_member, save_users
from rendering.cards import pil_to_discord_file
from rendering.museum import build_museum_image


class MuseumBgSelect(discord.ui.Select):
    def __init__(self, owner_id: int, owned_bgs: list):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label=k.capitalize(), value=k)
            for k in MUSEUM_BACKGROUNDS
        ]
        # fondos comprados
        if owned_bgs:
            catalog = load_museum_bg_catalog()
            for bg_id in owned_bgs:
                meta = catalog.get(str(bg_id), {})
                name = meta.get("name", f"Fondo {bg_id}")
                options.append(discord.SelectOption(
                    label=f"🏛️ {name}", value=f"custom:{bg_id}"
                ))
        super().__init__(placeholder="Cambiar fondo del museo…", options=options[:25], row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ese museo no es tuyo.", ephemeral=True)
            return

        bg = self.values[0]
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        uid      = str(interaction.user.id)
        ensure_user(users, uid)
        users[uid]["museum_bg"] = bg
        save_users(users)

        museum    = users[uid].get("museum", [None] * 10)
        inst_list = []
        for slot_code in museum:
            if slot_code is None:
                inst_list.append(None)
            else:
                inst_list.append(
                    find_instance_by_code(users[uid].get("cards", []), str(slot_code).lower())
                )

        img = build_museum_image(cards_db, inst_list, bg_key=bg)
        f   = pil_to_discord_file(img, "museo.png")
        e   = discord.Embed(
            title=f"🏛️ Museo de {interaction.user.display_name}",
            color=0x2c3e50,
        ).set_image(url="attachment://museo.png")
        await interaction.response.edit_message(embed=e, attachments=[f], view=self.view)


class MuseumView(discord.ui.View):
    def __init__(self, owner_id: int, owned_bgs: list = None):
        super().__init__(timeout=180)
        self.add_item(MuseumBgSelect(owner_id, owned_bgs or []))


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

        img  = build_museum_image(cards_db, inst_list, bg_key=bg_key)
        f    = pil_to_discord_file(img, "museo.png")
        e    = discord.Embed(
            title=f"🏛️ Museo de {target.display_name}",
            color=0x2c3e50,
        ).set_image(url="attachment://museo.png")
        owned_bgs = get_user_owned_bgs(users, str(ctx.author.id))
        view = MuseumView(ctx.author.id, owned_bgs) if target.id == ctx.author.id else None
        await ctx.reply(embed=e, file=f, view=view)

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
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)

        if bg.startswith("custom:"):
            bg_id = bg[7:]
            owned = get_user_owned_bgs(users, uid)
            if str(bg_id) not in [str(o) for o in owned]:
                await ctx.reply("No tenés ese fondo comprado.")
                return
            users[uid]["museum_bg"] = bg
            save_users(users)
            await ctx.reply(f"✅ Fondo del museo cambiado al fondo comprado **{bg_id}**.")
        elif bg in MUSEUM_BACKGROUNDS:
            users[uid]["museum_bg"] = bg
            save_users(users)
            await ctx.reply(f"✅ Fondo del museo cambiado a **{bg}**.")
        else:
            opts = ", ".join(MUSEUM_BACKGROUNDS.keys())
            await ctx.reply(f"Fondo inválido. Opciones: {opts}\nO usá `!pmset custom:<id>` para un fondo comprado.")

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

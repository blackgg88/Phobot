from __future__ import annotations

import discord
from discord.ext import commands

from config import MUSEUM_BACKGROUNDS
from core.cards import find_instance_by_code, migrate_users_cards, normalize_cards
from core.museum_bgs import get_user_owned_bgs_for_museum, load_museum_bg_catalog
from core.storage import get_paths, load_json
from core.users import ensure_user, pick_target_member, save_users
from rendering.cards import pil_to_discord_file
from rendering.museum3 import build_museum3_image, MUSEUM3_SLOTS


class Museum3BgSelect(discord.ui.Select):
    def __init__(self, owner_id: int, owned_bgs: list):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label=k.capitalize(), value=k)
            for k in MUSEUM_BACKGROUNDS
        ]
        if owned_bgs:
            catalog = load_museum_bg_catalog()
            for bg_id in owned_bgs:
                meta = catalog.get(str(bg_id), {})
                name = meta.get("name", f"Fondo {bg_id}")
                options.append(discord.SelectOption(
                    label=f"🏛️ {name}", value=f"custom:{bg_id}"
                ))
        super().__init__(placeholder="Cambiar fondo del museo III…", options=options[:25], row=0)

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
        users[uid]["museum3_bg"] = bg
        save_users(users)

        museum    = users[uid].get("museum3", [None] * MUSEUM3_SLOTS)
        inst_list = []
        for slot_code in museum:
            if slot_code is None:
                inst_list.append(None)
            else:
                inst_list.append(
                    find_instance_by_code(users[uid].get("cards", []), str(slot_code).lower())
                )

        img = build_museum3_image(cards_db, inst_list, bg_key=bg)
        f   = pil_to_discord_file(img, "museo3.png")
        e   = discord.Embed(
            title=f"🏛️ Museo III de {interaction.user.display_name}",
            color=0x2c3e50,
        ).set_image(url="attachment://museo3.png")
        await interaction.response.edit_message(embed=e, attachments=[f], view=self.view)


class Museum3View(discord.ui.View):
    def __init__(self, owner_id: int, owned_bgs: list = None):
        super().__init__(timeout=180)
        self.add_item(Museum3BgSelect(owner_id, owned_bgs or []))


class Museum3Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    @commands.command(name="pmuseo3")
    async def pmuseo3_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target = pick_target_member(ctx, member) or ctx.author
        users, cards_db = self._load()
        uid = str(target.id)
        ensure_user(users, uid)

        museum = users[uid].get("museum3", [None] * MUSEUM3_SLOTS)
        bg_key = users[uid].get("museum3_bg", "negro")
        inst_list = []
        for slot_code in museum:
            if slot_code is None:
                inst_list.append(None)
            else:
                inst_list.append(
                    find_instance_by_code(users[uid].get("cards", []), str(slot_code).lower())
                )

        img  = build_museum3_image(cards_db, inst_list, bg_key=bg_key)
        f    = pil_to_discord_file(img, "museo3.png")
        e    = discord.Embed(
            title=f"🏛️ Museo III de {target.display_name}",
            color=0x2c3e50,
        ).set_image(url="attachment://museo3.png")
        owned_bgs = get_user_owned_bgs_for_museum(users, str(ctx.author.id), 3)
        view = Museum3View(ctx.author.id, owned_bgs) if target.id == ctx.author.id else None
        await ctx.reply(embed=e, file=f, view=view)

    @commands.command(name="pmadd3")
    async def pmadd3_cmd(self, ctx: commands.Context, code: str = "", slot: str = "") -> None:
        if not code or not slot:
            await ctx.reply(f"Uso: `!pmadd3 <código> <slot 1-{MUSEUM3_SLOTS}>`")
            return
        try:
            slot_idx = int(slot) - 1
            assert 0 <= slot_idx < MUSEUM3_SLOTS
        except Exception:
            await ctx.reply(f"El slot debe ser un número entre 1 y {MUSEUM3_SLOTS}.")
            return

        users, cards_db = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        inst = find_instance_by_code(users[uid].get("cards", []), code.strip().lower())
        if not inst:
            await ctx.reply(f"No encontré la carta `{code}` en tu inventario.")
            return

        museum = users[uid].setdefault("museum3", [None] * MUSEUM3_SLOTS)
        while len(museum) < MUSEUM3_SLOTS:
            museum.append(None)
        museum[slot_idx] = inst.get("code")
        save_users(users)
        await ctx.reply(f"✅ `{inst.get('name')}` puesto en el slot **{slot_idx + 1}** del museo III.")

    @commands.command(name="pmremove3")
    async def pmremove3_cmd(self, ctx: commands.Context, slot: str = "") -> None:
        if not slot:
            await ctx.reply(f"Uso: `!pmremove3 <slot 1-{MUSEUM3_SLOTS}>`")
            return
        try:
            slot_idx = int(slot) - 1
            assert 0 <= slot_idx < MUSEUM3_SLOTS
        except Exception:
            await ctx.reply(f"El slot debe ser entre 1 y {MUSEUM3_SLOTS}.")
            return

        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        museum = users[uid].setdefault("museum3", [None] * MUSEUM3_SLOTS)
        while len(museum) < MUSEUM3_SLOTS:
            museum.append(None)
        museum[slot_idx] = None
        save_users(users)
        await ctx.reply(f"✅ Slot **{slot_idx + 1}** del museo III vaciado.")

    @commands.command(name="pmclear3")
    async def pmclear3_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        users[uid]["museum3"] = [None] * MUSEUM3_SLOTS
        save_users(users)
        await ctx.reply("✅ Museo III limpiado.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Museum3Cog(bot))

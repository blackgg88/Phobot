from __future__ import annotations

from typing import List, Optional

import discord
from discord.ext import commands

from core.achievements import (
    ACHIEVEMENTS, ACH_BY_ID, ensure_guild_stats,
)
from core.clock import now_ar, format_ar
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from rendering.cards import pil_to_discord_file
from rendering.profile import get_season_ar, render_profile_image


# ── Storage helpers ────────────────────────────────────────

def _load():
    users_path, cards_path, _ = get_paths()
    from core.cards import normalize_cards
    users    = load_json(users_path, {})
    cards_db = normalize_cards(load_json(cards_path, {}))
    return users, cards_db


def _profile_stats(users: dict, uid: str, gid: str) -> dict:
    ensure_user(users, uid)
    stats = ensure_guild_stats(users, uid, gid)
    stats.setdefault("profile", {
        "birthday":        "",
        "age":             "",
        "featured_titles": [],
        "featured_cards":  [],
    })
    p = stats["profile"]
    p.setdefault("birthday",        "")
    p.setdefault("age",             "")
    p.setdefault("featured_titles", [])
    p.setdefault("featured_cards",  [])
    return stats


def _find_card_by_code(cards: list, code: str) -> Optional[dict]:
    code = code.strip().lower()
    for c in cards:
        if isinstance(c, dict) and str(c.get("code", "")).strip().lower() == code:
            return c
    return None


def _resolve_featured_cards(users: dict, cards_db: dict, uid: str, codes: List[str]) -> List[Optional[dict]]:
    inventory = users.get(uid, {}).get("cards", [])
    result = []
    for code in codes[:3]:
        inst = _find_card_by_code(inventory, code)
        if inst:
            col  = inst.get("collection")
            name = inst.get("name")
            meta = (cards_db.get(col) or {}).get(name) or {}
            result.append({
                "name":       name,
                "collection": col,
                "rarity":     inst.get("rarity") or meta.get("rarity") or "common",
                "img":        meta.get("img"),
            })
        else:
            result.append(None)
    return result


# ── Render helper ──────────────────────────────────────────

async def _build_file(
    member: discord.Member,
    users: dict,
    cards_db: dict,
    uid: str,
    gid: str,
) -> discord.File:
    stats   = _profile_stats(users, uid, gid)
    profile = stats["profile"]
    unlocked = set(stats.get("achievements", []))

    ar = now_ar()
    season_key   = get_season_ar(ar.month, ar.day)
    date_str     = format_ar("%d/%m/%Y")
    time_str     = format_ar("%H:%M")

    # avatar
    try:
        avatar_bytes = await member.display_avatar.read()
    except Exception:
        avatar_bytes = None

    featured_cards = _resolve_featured_cards(
        users, cards_db, uid, profile.get("featured_cards", [])
    )

    img = render_profile_image(
        avatar_bytes       = avatar_bytes,
        display_name       = member.display_name,
        birthday           = profile.get("birthday", ""),
        age                = profile.get("age", ""),
        achievements_done  = len(unlocked),
        achievements_total = len(ACHIEVEMENTS),
        featured_titles    = profile.get("featured_titles", []),
        featured_cards     = featured_cards,
        season_key         = season_key,
        date_str           = date_str,
        time_str           = time_str,
    )
    return pil_to_discord_file(img, "perfil.png")


# ── Modales ────────────────────────────────────────────────

class BirthdayModal(discord.ui.Modal, title="Establecer cumpleaños"):
    birthday = discord.ui.TextInput(
        label="Cumpleaños (DD/MM)",
        placeholder="Ej: 25/03",
        max_length=5,
        required=True,
    )

    def __init__(self, view: "ProfileView"):
        super().__init__()
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.birthday.value.strip()
        # validar formato DD/MM
        try:
            parts = raw.split("/")
            assert len(parts) == 2
            d, m = int(parts[0]), int(parts[1])
            assert 1 <= d <= 31 and 1 <= m <= 12
            value = f"{d:02d}/{m:02d}"
        except Exception:
            await interaction.response.send_message(
                "Formato inválido. Usá DD/MM (ej: 25/03).", ephemeral=True
            )
            return
        await self._view.save_profile(interaction, birthday=value)


class AgeModal(discord.ui.Modal, title="Establecer edad"):
    age = discord.ui.TextInput(
        label="Edad",
        placeholder="Ej: 22",
        max_length=3,
        required=True,
    )

    def __init__(self, view: "ProfileView"):
        super().__init__()
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.age.value.strip()
        if not raw.isdigit() or not (1 <= int(raw) <= 120):
            await interaction.response.send_message(
                "Ingresá un número de edad válido (1-120).", ephemeral=True
            )
            return
        await self._view.save_profile(interaction, age=raw)


class TitlesModal(discord.ui.Modal, title="Títulos destacados (hasta 4)"):
    t1 = discord.ui.TextInput(label="Título 1", required=False, max_length=60)
    t2 = discord.ui.TextInput(label="Título 2", required=False, max_length=60)
    t3 = discord.ui.TextInput(label="Título 3", required=False, max_length=60)
    t4 = discord.ui.TextInput(label="Título 4", required=False, max_length=60)

    def __init__(self, view: "ProfileView", current: list):
        super().__init__()
        self._view = view
        for field, val in zip([self.t1, self.t2, self.t3, self.t4], current):
            ach = ACH_BY_ID.get(val)
            if ach:
                field.default = ach["title"]

    async def on_submit(self, interaction: discord.Interaction):
        unlocked = self._view.unlocked_set()
        inputs   = [self.t1.value, self.t2.value, self.t3.value, self.t4.value]
        ids      = []
        for raw in inputs:
            raw = raw.strip()
            if not raw:
                continue
            # buscar por nombre exacto (case-insensitive) entre logros desbloqueados
            match = next(
                (a["id"] for a in ACHIEVEMENTS
                 if a["title"].lower() == raw.lower() and a["id"] in unlocked),
                None,
            )
            if match:
                ids.append(match)
            else:
                await interaction.response.send_message(
                    f'No encontré el logro **"{raw}"** entre tus logros desbloqueados.',
                    ephemeral=True,
                )
                return
        await self._view.save_profile(interaction, featured_titles=ids)


class CardsModal(discord.ui.Modal, title="Cartas destacadas (hasta 3)"):
    c1 = discord.ui.TextInput(label="Código de carta 1", required=False, max_length=10)
    c2 = discord.ui.TextInput(label="Código de carta 2", required=False, max_length=10)
    c3 = discord.ui.TextInput(label="Código de carta 3", required=False, max_length=10)

    def __init__(self, view: "ProfileView", current: list):
        super().__init__()
        self._view = view
        for field, code in zip([self.c1, self.c2, self.c3], current):
            field.default = code

    async def on_submit(self, interaction: discord.Interaction):
        codes = [
            v.value.strip().lower()
            for v in [self.c1, self.c2, self.c3]
            if v.value.strip()
        ]
        users, cards_db = _load()
        uid = str(interaction.user.id)
        inventory = users.get(uid, {}).get("cards", [])
        for code in codes:
            if not _find_card_by_code(inventory, code):
                await interaction.response.send_message(
                    f"No tenés ninguna carta con código `{code}`.", ephemeral=True
                )
                return
        await self._view.save_profile(interaction, featured_cards=codes)


# ── View ───────────────────────────────────────────────────

class ProfileView(discord.ui.View):
    def __init__(self, *, owner_id: int, target_uid: str, guild_id: str):
        super().__init__(timeout=300)
        self.owner_id  = owner_id
        self.target_uid = target_uid
        self.guild_id  = guild_id

    def unlocked_set(self):
        users, _ = _load()
        ensure_user(users, self.target_uid)
        stats = ensure_guild_stats(users, self.target_uid, self.guild_id)
        return set(stats.get("achievements", []))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Solo el dueño del perfil puede editarlo.", ephemeral=True
            )
            return False
        return True

    async def save_profile(self, interaction: discord.Interaction, **kwargs):
        users, cards_db = _load()
        uid  = self.target_uid
        gid  = self.guild_id
        ensure_user(users, uid)
        stats   = _profile_stats(users, uid, gid)
        profile = stats["profile"]
        for k, v in kwargs.items():
            profile[k] = v
        save_users(users)

        member = interaction.guild.get_member(int(uid))
        if member is None:
            try:
                member = await interaction.guild.fetch_member(int(uid))
            except Exception:
                await interaction.response.send_message("Error al cargar el miembro.", ephemeral=True)
                return

        f = await _build_file(member, users, cards_db, uid, gid)
        await interaction.response.edit_message(attachments=[f], view=self)

    @discord.ui.button(label="✏ Cumpleaños", style=discord.ButtonStyle.secondary, row=0)
    async def btn_birthday(self, interaction: discord.Interaction, _):
        users, _ = _load()
        stats    = _profile_stats(users, self.target_uid, self.guild_id)
        await interaction.response.send_modal(
            BirthdayModal(self)
        )

    @discord.ui.button(label="✏ Edad", style=discord.ButtonStyle.secondary, row=0)
    async def btn_age(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(AgeModal(self))

    @discord.ui.button(label="🏆 Títulos", style=discord.ButtonStyle.primary, row=0)
    async def btn_titles(self, interaction: discord.Interaction, _):
        users, _ = _load()
        stats    = _profile_stats(users, self.target_uid, self.guild_id)
        current  = stats["profile"].get("featured_titles", [])
        await interaction.response.send_modal(TitlesModal(self, current))

    @discord.ui.button(label="🃏 Cartas", style=discord.ButtonStyle.primary, row=0)
    async def btn_cards(self, interaction: discord.Interaction, _):
        users, _ = _load()
        stats    = _profile_stats(users, self.target_uid, self.guild_id)
        current  = stats["profile"].get("featured_cards", [])
        await interaction.response.send_modal(CardsModal(self, current))

    @discord.ui.button(label="Ver mis logros", style=discord.ButtonStyle.secondary, row=1)
    async def btn_achievements(self, interaction: discord.Interaction, _):
        unlocked = self.unlocked_set()
        lines    = []
        cat      = None
        for ach in ACHIEVEMENTS:
            if ach["cat"] != cat:
                cat = ach["cat"]
                lines.append(f"\n{cat}")
            tick = "✅" if ach["id"] in unlocked else "⬜"
            lines.append(f"{tick} **{ach['title']}**")
        e = discord.Embed(
            title="🏆 Tus logros desbloqueados",
            description="\n".join(lines),
            color=0xf1c40f,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)


# ── Cog ────────────────────────────────────────────────────

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="pperfil")
    async def pperfil_cmd(
        self, ctx: commands.Context, *, member: discord.Member = None
    ) -> None:
        target = member or ctx.author
        uid    = str(target.id)
        gid    = str(ctx.guild.id)

        users, cards_db = _load()
        _profile_stats(users, uid, gid)
        save_users(users)

        f = await _build_file(target, users, cards_db, uid, gid)

        # solo el dueño puede editar su propio perfil
        owner_id = ctx.author.id
        view = ProfileView(owner_id=owner_id, target_uid=uid, guild_id=gid)
        if ctx.author != target:
            # si alguien está viendo el perfil de otro, no muestra botones de edición
            view = None

        e = discord.Embed(color=0x2f3136)
        e.set_image(url="attachment://perfil.png")
        await ctx.reply(embed=e, file=f, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))

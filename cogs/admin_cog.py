from __future__ import annotations

import discord
from discord.ext import commands

from config import OWNER_ID
from core.cards import migrate_users_cards, normalize_cards
from core.events import load_events_config, save_events_config, load_events, load_shop_collections
from core.frames import load_frames_catalog
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users


def _owner_only():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    # ─── Gold ─────────────────────────────────────────────────────────────────

    @commands.command(name="givegold")
    @_owner_only()
    async def givegold_cmd(self, ctx, member: discord.Member, amount: int) -> None:
        users, _ = self._load()
        uid = str(member.id)
        ensure_user(users, uid)
        users[uid]["gold"] = int(users[uid].get("gold", 0)) + amount
        save_users(users)
        await ctx.reply(f"✅ Dado **{amount}** oro a {member.display_name}. Total: **{users[uid]['gold']}**")

    @commands.command(name="setgold")
    @_owner_only()
    async def setgold_cmd(self, ctx, member: discord.Member, amount: int) -> None:
        users, _ = self._load()
        uid = str(member.id)
        ensure_user(users, uid)
        users[uid]["gold"] = amount
        save_users(users)
        await ctx.reply(f"✅ Oro de {member.display_name} establecido en **{amount}**.")

    # ─── Frames ───────────────────────────────────────────────────────────────

    @commands.command(name="giveframe")
    @_owner_only()
    async def giveframe_cmd(self, ctx, member: discord.Member, frame_id: int) -> None:
        users, _ = self._load()
        uid  = str(member.id)
        ensure_user(users, uid)
        catalog = load_frames_catalog()
        if frame_id not in catalog:
            await ctx.reply(f"No existe el marco ID **{frame_id}**.")
            return
        users[uid].setdefault("frames", []).append(frame_id)
        save_users(users)
        await ctx.reply(f"✅ Marco **{catalog[frame_id]['name']}** (ID {frame_id}) dado a {member.display_name}.")

    # ─── Packs ────────────────────────────────────────────────────────────────

    @commands.command(name="givepack")
    @_owner_only()
    async def givepack_cmd(self, ctx, member: discord.Member, rarity: str, amount: int = 1) -> None:
        VALID = ["common", "rare", "epic", "legendary", "mythic"]
        rarity = rarity.lower()
        if rarity not in VALID:
            await ctx.reply(f"Rareza inválida. Opciones: {', '.join(VALID)}")
            return
        users, _ = self._load()
        uid = str(member.id)
        ensure_user(users, uid)
        users[uid].setdefault("packs", {})[rarity] = int(users[uid]["packs"].get(rarity, 0)) + amount
        save_users(users)
        await ctx.reply(f"✅ Dado **{amount}x sobre {rarity}** a {member.display_name}.")

    # ─── Events ───────────────────────────────────────────────────────────────

    @commands.command(name="eventshow")
    @_owner_only()
    async def eventshow_cmd(self, ctx) -> None:
        cfg = load_events_config()
        e = discord.Embed(title="📅 Config de Eventos", color=0x3498db)
        e.add_field(name="Activo", value=str(cfg.get("active", False)), inline=True)
        e.add_field(name="Colecciones activas", value=", ".join(cfg.get("active_collections", [])) or "ninguna", inline=False)
        e.add_field(name="Baneadas", value=", ".join(cfg.get("disabled_collections", [])) or "ninguna", inline=False)
        await ctx.reply(embed=e)

    @commands.command(name="eventset")
    @_owner_only()
    async def eventset_cmd(self, ctx, state: str) -> None:
        cfg = load_events_config()
        cfg["active"] = state.lower() in ("on", "true", "1", "si")
        save_events_config(**cfg)
        await ctx.reply(f"✅ Eventos: **{'activados' if cfg['active'] else 'desactivados'}**.")

    @commands.command(name="eventadd")
    @_owner_only()
    async def eventadd_cmd(self, ctx, *, col: str) -> None:
        cfg = load_events_config()
        cols = cfg.setdefault("active_collections", [])
        if col not in cols:
            cols.append(col)
        save_events_config(**cfg)
        await ctx.reply(f"✅ `{col}` agregada a eventos.")

    @commands.command(name="eventremove")
    @_owner_only()
    async def eventremove_cmd(self, ctx, *, col: str) -> None:
        cfg = load_events_config()
        cols = cfg.get("active_collections", [])
        if col in cols:
            cols.remove(col)
        save_events_config(**cfg)
        await ctx.reply(f"✅ `{col}` quitada de eventos.")

    @commands.command(name="eventban")
    @_owner_only()
    async def eventban_cmd(self, ctx, *, col: str) -> None:
        cfg = load_events_config()
        bans = cfg.setdefault("disabled_collections", [])
        if col not in bans:
            bans.append(col)
        save_events_config(**cfg)
        await ctx.reply(f"✅ `{col}` baneada del gacha.")

    @commands.command(name="eventunban")
    @_owner_only()
    async def eventunban_cmd(self, ctx, *, col: str) -> None:
        cfg = load_events_config()
        bans = cfg.get("disabled_collections", [])
        if col in bans:
            bans.remove(col)
        save_events_config(**cfg)
        await ctx.reply(f"✅ `{col}` desbaneada.")

    @commands.command(name="eventclearbans")
    @_owner_only()
    async def eventclearbans_cmd(self, ctx) -> None:
        cfg = load_events_config()
        cfg["disabled_collections"] = []
        save_events_config(**cfg)
        await ctx.reply("✅ Todos los bans de eventos limpiados.")

    # ─── Shop ─────────────────────────────────────────────────────────────────

    @commands.command(name="shopshow")
    @_owner_only()
    async def shopshow_cmd(self, ctx) -> None:
        cfg = load_events_config()
        e = discord.Embed(title="🏪 Config de Tienda", color=0xe67e22)
        e.add_field(name="Activa", value=str(cfg.get("shop_active", False)), inline=True)
        e.add_field(name="Colecciones", value=", ".join(cfg.get("shop_collections", [])) or "ninguna", inline=False)
        await ctx.reply(embed=e)

    @commands.command(name="shopset")
    @_owner_only()
    async def shopset_cmd(self, ctx, state: str) -> None:
        cfg = load_events_config()
        cfg["shop_active"] = state.lower() in ("on", "true", "1", "si")
        save_events_config(**cfg)
        await ctx.reply(f"✅ Tienda: **{'activa' if cfg['shop_active'] else 'inactiva'}**.")

    @commands.command(name="shopadd")
    @_owner_only()
    async def shopadd_cmd(self, ctx, *, col: str) -> None:
        cfg = load_events_config()
        cols = cfg.setdefault("shop_collections", [])
        if col not in cols:
            cols.append(col)
        save_events_config(**cfg)
        await ctx.reply(f"✅ `{col}` agregada a la tienda.")

    @commands.command(name="shopremove")
    @_owner_only()
    async def shopremove_cmd(self, ctx, *, col: str) -> None:
        cfg = load_events_config()
        cols = cfg.get("shop_collections", [])
        if col in cols:
            cols.remove(col)
        save_events_config(**cfg)
        await ctx.reply(f"✅ `{col}` quitada de la tienda.")

    @commands.command(name="shopclear")
    @_owner_only()
    async def shopclear_cmd(self, ctx) -> None:
        cfg = load_events_config()
        cfg["shop_collections"] = []
        save_events_config(**cfg)
        await ctx.reply("✅ Tienda limpiada.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))

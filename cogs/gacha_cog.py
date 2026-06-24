from __future__ import annotations

import time
from typing import List

import discord
from discord.ext import commands

from config import COOLDOWN, DROP_COOLDOWN, TOKEN_DROP_CHANCE
from core.cards import build_active_pool, create_card_instance_from_meta, migrate_users_cards, normalize_cards, pick_unique, rarity_es
from core.events import load_events
from core.storage import get_paths, load_json
from core.tokens import gen_unique_token_code, all_existing_token_codes, load_tokens_db
from core.users import ensure_user, human_time, save_users
from rendering.cards import pil_to_discord_file
from rendering.pack import create_pack_image, create_drop_image, create_single_drop_card
from views.drop import MultiDropView, RARITY_EMOJI

import random


async def notify_wishlist(bot: commands.Bot, channel: discord.TextChannel,
                          pulled: List[dict], users: dict) -> None:
    for c in pulled:
        collection = c.get("collection")
        name       = c.get("name")
        if not collection or not name:
            continue
        for uid, udata in users.items():
            wl = udata.get("wishlist", [])
            if any(w.lower() == name.lower() for w in wl):
                try:
                    user = await bot.fetch_user(int(uid))
                    await channel.send(
                        f"🌟 {user.mention}, ¡**{name}** (*{collection}*) apareció en el gacha/drop!"
                    )
                except Exception:
                    pass


class GachaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    @commands.command(name="pgacha")
    async def pgacha_cmd(self, ctx: commands.Context) -> None:
        users, cards_db = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)

        now  = time.time()
        last = users[uid].get("last_gacha", 0)
        rem  = COOLDOWN - (now - last)
        if rem > 0:
            await ctx.reply(f"⏰ Gacha en cooldown. Volvé en **{human_time(int(rem))}**.")
            return

        active = load_events(cards_db)
        if not active:
            await ctx.reply("No hay colecciones activas en el gacha.")
            return

        pool, weights = build_active_pool(cards_db, active)
        if not pool:
            await ctx.reply("No hay cartas en el pool activo.")
            return

        pulled = pick_unique(pool, weights, k=5)
        if not pulled:
            await ctx.reply("No se pudieron obtener cartas únicas.")
            return

        tokens_db = load_tokens_db()
        existing_tokens = all_existing_token_codes(users)

        pack_data = []
        for meta in pulled:
            col  = meta["collection"]
            name = meta["name"]
            inst = create_card_instance_from_meta(col, name, cards_db, users)
            is_token = random.random() < TOKEN_DROP_CHANCE

            if is_token:
                from core.tokens import flatten_tokens_db, token_variants_for
                variants = token_variants_for(cards_db, tokens_db, collection=col, name=name)
                if variants:
                    tok_img  = random.choice(variants)
                    tok_code = gen_unique_token_code(existing_tokens)
                    existing_tokens.add(tok_code)
                    tok_inst = {"code": tok_code, "collection": col, "name": name, "img": tok_img}
                    users[uid].setdefault("tokens", []).append(tok_inst)
                    inst["token_code"] = tok_code
                    inst["token_img"]  = tok_img
                    pack_data.append({**meta, "img": tok_img, "value": inst["value"], "is_token": True})
                    continue

            users[uid].setdefault("cards", []).append(inst)
            pack_data.append({**meta, "value": inst["value"]})

        users[uid]["last_gacha"] = now
        save_users(users)

        img = create_pack_image(pack_data[:5])
        f   = pil_to_discord_file(img, "gacha.png")
        e   = discord.Embed(
            title=f"🎴 {ctx.author.display_name} abrió el gacha",
            color=0x9b59b6,
        ).set_image(url="attachment://gacha.png")
        await ctx.reply(embed=e, file=f)
        await notify_wishlist(self.bot, ctx.channel, pack_data, users)

    @commands.command(name="pdrop")
    async def pdrop_cmd(self, ctx: commands.Context) -> None:
        users, cards_db = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)

        now  = time.time()
        last = users[uid].get("last_drop", 0)
        rem  = DROP_COOLDOWN - (now - last)
        if rem > 0:
            await ctx.reply(f"⏰ Drop en cooldown. Volvé en **{human_time(int(rem))}**.")
            return

        active = load_events(cards_db)
        if not active:
            await ctx.reply("No hay colecciones activas.")
            return

        pool, weights = build_active_pool(cards_db, active)
        if not pool:
            await ctx.reply("No hay cartas en el pool.")
            return

        dropped = pick_unique(pool, weights, k=3) or []
        if not dropped:
            await ctx.reply("No hay cartas disponibles para el drop.")
            return

        users[uid]["last_drop"] = now
        from core.missions import progress as mission_progress
        from core.bot_channel import get_bot_channel
        newly_missions = mission_progress(users, uid, "drops", 1)
        save_users(users)
        for label, reward in newly_missions:
            users[uid]["gold"] = int(users[uid].get("gold", 0)) + reward
            save_users(users)
            ch = get_bot_channel(ctx.guild) or ctx.channel
            await ch.send(f"✅ {ctx.author.mention} completó la misión **{label}** — **+{reward}** oro 💰")

        pack_data = []
        for idx, m in enumerate(dropped):
            display_val = random.randint(1, 9999)
            pack_data.append({
                "collection":   m["collection"],
                "name":         m["name"],
                "img":          m["img"],
                "rarity":       m["rarity"],
                "display_code": f"G·{display_val}",
            })

        img  = create_drop_image(pack_data)
        f    = pil_to_discord_file(img, "drop.png")
        view = MultiDropView(drop_user_id=ctx.author.id, cards=pack_data, drop_time=now)
        await ctx.send(
            content=f"**{ctx.author.display_name} está dropeando cartas**",
            file=f,
            view=view,
        )
        await notify_wishlist(self.bot, ctx.channel, pack_data, users)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GachaCog(bot))

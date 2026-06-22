from __future__ import annotations

import random
import time

import discord
from discord.ext import commands

from config import DAILY_COOLDOWN, DAILY_REWARD, SELL_VALUES, WORK_COOLDOWN, WORK_MAX, WORK_MIN
from core.cards import find_instance_by_code, migrate_users_cards, normalize_cards, rarity_from_cards_db
from core.storage import get_paths, load_json
from core.users import counts_by_char, ensure_user, human_time, pick_target_member, save_users
from rendering.cards import pil_to_discord_file, render_single_card_image
from views.sell import SellConfirmView, SellDuplicatesView


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    @commands.command(name="pdaily")
    async def pdaily_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)

        now  = time.time()
        last = users[uid].get("last_daily", 0)
        rem  = DAILY_COOLDOWN - (now - last)
        if rem > 0:
            await ctx.reply(f"⏰ Daily en cooldown. Volvé en **{human_time(int(rem))}**.")
            return

        users[uid]["gold"] = int(users[uid].get("gold", 0)) + DAILY_REWARD
        users[uid]["last_daily"] = now
        save_users(users)
        await ctx.reply(f"✅ Daily reclamado: **+{DAILY_REWARD}** oro 💰\nOro actual: **{users[uid]['gold']}**")

    @commands.command(name="pwork")
    async def pwork_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)

        now  = time.time()
        last = users[uid].get("last_work", 0)
        rem  = WORK_COOLDOWN - (now - last)
        if rem > 0:
            await ctx.reply(f"⏰ Work en cooldown. Volvé en **{human_time(int(rem))}**.")
            return

        earned = random.randint(WORK_MIN, WORK_MAX)
        users[uid]["gold"] = int(users[uid].get("gold", 0)) + earned
        users[uid]["last_work"] = now
        save_users(users)
        await ctx.reply(f"💼 Trabajaste y ganaste **{earned}** oro 💰\nOro actual: **{users[uid]['gold']}**")

    @commands.command(name="pvender")
    async def pvender_cmd(self, ctx: commands.Context, *args) -> None:
        users, cards_db = self._load()
        uid = str(ctx.author.id)

        target = await pick_target_member(ctx, None)
        target_uid = str(target.id) if target else uid
        ensure_user(users, target_uid)

        # pvender rep [@user]
        if args and args[0].lower() == "rep":
            card_instances = users[target_uid].get("cards", [])
            gold           = int(users[target_uid].get("gold", 0))
            view = SellDuplicatesView(
                viewer_id=ctx.author.id,
                target_user_id=target_uid,
                cards_db=cards_db,
                card_instances=card_instances,
                gold=gold,
            )
            counts = counts_by_char(card_instances)
            has_dups = any(q > 1 for q in counts.values())
            if not has_dups:
                await ctx.reply("No tenés cartas repetidas.")
                return
            await ctx.reply(embed=view.make_embed(), view=view)
            return

        if not args:
            await ctx.reply("Uso: `pvender <código>` o `pvender rep`")
            return

        code = args[0].strip().lower()
        ensure_user(users, uid)
        inst = find_instance_by_code(users[uid].get("cards", []), code)
        if not inst:
            await ctx.reply(f"No encontré la carta `{code}` en tu inventario.")
            return

        rarity = (inst.get("rarity") or rarity_from_cards_db(cards_db, inst.get("collection"), inst.get("name")) or "common").lower()
        gain   = SELL_VALUES.get(rarity, 1)
        img    = render_single_card_image(cards_db, inst)
        f      = pil_to_discord_file(img, "sell_preview.png")

        view = SellConfirmView(
            viewer_id=ctx.author.id,
            code=code,
            inst_snapshot=dict(inst),
            rarity=rarity,
            gain=gain,
            cards_db=cards_db,
        )
        e = discord.Embed(
            title="💰 Vender carta",
            description=f"Carta: **{inst.get('name')}** (*{inst.get('collection')}*)\nRareza: `{rarity}` | Ganancia: **{gain}** oro\n¿Confirmar?",
            color=0xf1c40f,
        ).set_image(url="attachment://sell_preview.png")
        msg = await ctx.reply(embed=e, file=f, view=view)
        view.message = msg


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))

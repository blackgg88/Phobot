from __future__ import annotations

import discord
from discord.ext import commands

from core.cards import (
    choose_match_by_number, find_card_matches, find_instance_by_code,
    migrate_users_cards, normalize_cards, rarity_es,
)
from core.storage import get_paths, load_json
from core.users import ensure_user, pick_target_member, save_users, user_owned_pairs, user_holo_pairs
from rendering.cards import pil_to_discord_file, render_single_card_image
from rendering.fx import HOLO_GEN_THRESHOLD
from rendering.pack import render_pver_card
from views.album import CollectionPager, SingleCollectionPager
from views.cards_list import CardsListView
from views.frames_view import ConfirmRemoveFrameView, PVerFrameView


class CollectionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    @commands.command(name="palbums")
    async def palbums_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target = pick_target_member(ctx, member)
        target = target or ctx.author
        users, cards_db = self._load()
        uid = str(target.id)
        ensure_user(users, uid)

        if not cards_db:
            await ctx.reply("No hay colecciones cargadas.")
            return

        cards     = users[uid].get("cards", [])
        owned_set = user_owned_pairs(cards)
        holo_set  = user_holo_pairs(cards)
        view      = CollectionPager(
            viewer_id=ctx.author.id,
            target_user_id=uid,
            collection_names=list(cards_db.keys()),
            cards_db=cards_db,
            owned_set=owned_set,
            holo_set=holo_set,
        )
        f, tp  = view.build_file()
        embed  = view.make_embed(preview_pages=tp)
        await ctx.reply(embed=embed, file=f, view=view)

    @commands.command(name="palbum")
    async def palbum_cmd(self, ctx: commands.Context, *, args: str = "") -> None:
        parts  = args.strip().split()
        target = ctx.author

        # Check if last arg is a mention
        if parts and parts[-1].startswith("<@"):
            try:
                uid_str = parts[-1].strip("<@!>")
                target  = ctx.guild.get_member(int(uid_str)) or ctx.author
                parts   = parts[:-1]
            except Exception:
                pass

        col_query = " ".join(parts).strip()
        users, cards_db = self._load()
        uid = str(target.id)
        ensure_user(users, uid)

        if not col_query:
            await ctx.reply("Especificá el nombre de la colección. Ej: `palbum Nombre Colección`")
            return

        col_name = col_query
        if col_name not in cards_db:
            matches = [k for k in cards_db if col_query.lower() in k.lower()]
            if len(matches) == 1:
                col_name = matches[0]
            elif len(matches) > 1:
                options = "\n".join(f"• {m}" for m in matches[:10])
                await ctx.reply(f"Encontré varias colecciones:\n{options}\nSé más específico.")
                return
            else:
                await ctx.reply(f"No encontré la colección `{col_query}`.")
                return

        cards     = users[uid].get("cards", [])
        owned_set = user_owned_pairs(cards)
        holo_set  = user_holo_pairs(cards)
        view      = SingleCollectionPager(
            viewer_id=ctx.author.id,
            target_user_id=uid,
            collection_name=col_name,
            cards_db=cards_db,
            owned_set=owned_set,
            holo_set=holo_set,
        )
        f     = view.build_file()
        embed = view.make_embed()
        await ctx.reply(embed=embed, file=f, view=view)

    @commands.command(name="pcartas")
    async def pcartas_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target = member or ctx.author
        users, cards_db = self._load()
        uid = str(target.id)
        ensure_user(users, uid)

        view  = CardsListView(viewer_id=ctx.author.id)
        cards = users[uid].get("cards", [])
        embed = view.build_embed(cards)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="pver")
    async def pver_cmd(self, ctx: commands.Context, code: str = "") -> None:
        if not code:
            await ctx.reply("Uso: `pver <código>`")
            return

        code  = code.strip().lower()
        users, cards_db = self._load()
        uid   = str(ctx.author.id)
        ensure_user(users, uid)

        inst = find_instance_by_code(users[uid].get("cards", []), code)
        if not inst:
            await ctx.reply(f"No encontré la carta `{code}` en tu inventario.")
            return

        has_frame  = inst.get("frame_id") is not None
        has_token  = inst.get("token_code") is not None
        rarity_str = rarity_es(inst.get("rarity", "common"))
        gen        = inst.get("gen")
        gen_str    = f"G·{gen}" if gen is not None else None
        is_holo    = gen is not None and int(gen) <= HOLO_GEN_THRESHOLD

        desc = f"Código: `{code}` | Rareza: **{rarity_str}**"
        if gen_str:
            desc += f"\nGeneración: **{gen_str}**" + (" ✨" if is_holo else "")
        if has_frame:
            desc += f"\nMarco ID: **{inst['frame_id']}**"
        if has_token:
            desc += f"\nToken: `{inst['token_code']}`"

        color = 0xc084fc if is_holo else 0x2ecc71

        # render estilo drop (con nombre, serie y G)
        img = render_pver_card(cards_db, inst)
        f   = pil_to_discord_file(img, "card.png")

        e = discord.Embed(
            title=f"{'✨ ' if is_holo else '🃏 '}{inst.get('name')} — {inst.get('collection')}",
            description=desc,
            color=color,
        ).set_image(url="attachment://card.png")

        view = PVerFrameView(user_id=ctx.author.id, inst=inst, cards_db=cards_db) if has_frame else None

        if view:
            if has_frame:
                remove_view = ConfirmRemoveFrameView(user_id=ctx.author.id, inst=inst, cards_db=cards_db)
                await ctx.reply(embed=e, file=f, view=remove_view)
            else:
                await ctx.reply(embed=e, file=f, view=view)
        else:
            await ctx.reply(embed=e, file=f)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CollectionCog(bot))

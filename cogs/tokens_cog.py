from __future__ import annotations

from discord.ext import commands

from core.cards import find_card_matches, choose_match_by_number, migrate_users_cards, normalize_cards
from core.storage import get_paths, load_json
from core.tokens import load_tokens_db, token_variants_for
from core.users import ensure_user, save_users
from rendering.cards import pil_to_discord_file
from rendering.lookup import build_plu_image
from views.tokens_view import TokensListView


class TokensCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    @commands.command(name="ptokens")
    async def ptokens_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid = str(ctx.author.id)
        ensure_user(users, uid)
        tokens = users[uid].get("tokens", [])
        view   = TokensListView(user_id=ctx.author.id, tokens=tokens)
        await ctx.reply(embed=view.make_embed(), view=view)

    @commands.command(name="plu")
    async def plu_cmd(self, ctx: commands.Context, *, query: str = "") -> None:
        if not query:
            await ctx.reply("Uso: `plu <nombre de carta>`")
            return

        users, cards_db = self._load()
        matches = find_card_matches(cards_db, query)

        if not matches:
            await ctx.reply(f"No encontré cartas con `{query}`.")
            return

        if len(matches) == 1:
            name, collection = matches[0]
        else:
            result = await choose_match_by_number(self.bot, ctx, matches, title="Lookup — ¿cuál querés ver?")
            if result is None:
                return
            name, collection = result

        tokens_db   = load_tokens_db()
        token_imgs  = token_variants_for(cards_db, tokens_db, collection=collection, name=name)
        img         = build_plu_image(cards_db, collection=collection, name=name, token_imgs=token_imgs)
        f           = pil_to_discord_file(img, "plu.png")

        import discord
        e = discord.Embed(
            title=f"🔍 Lookup — {name} ({collection})",
            description=f"Tokens disponibles: **{len(token_imgs)}**",
            color=0x3498db,
        ).set_image(url="attachment://plu.png")
        await ctx.reply(embed=e, file=f)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TokensCog(bot))

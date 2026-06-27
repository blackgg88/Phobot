from __future__ import annotations

import discord
from discord.ext import commands

from config import BANNER_PULL_COST, BANNER_PULL10_COST
from core.banners import get_or_rotate_banners, get_banner, get_pity, do_pulls, apply_pull_results, preview_next_banners
from core.cards import migrate_users_cards, normalize_cards
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from rendering.banners import render_banners_image, render_pull_result
from rendering.cards import pil_to_discord_file


class NextBannersView(discord.ui.View):
    def __init__(self, cards_db: dict):
        super().__init__(timeout=120)
        self._cards_db = cards_db

    @discord.ui.button(label="Próximos banners", style=discord.ButtonStyle.secondary, emoji="🔮")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_b = preview_next_banners(self._cards_db)
        from rendering.banners import render_banners_image
        from rendering.cards import pil_to_discord_file
        img = render_banners_image(next_b, self._cards_db, next_mode=True)
        f   = pil_to_discord_file(img, "next_banners.png")
        e   = discord.Embed(color=0x9966cc).set_image(url="attachment://next_banners.png")
        await interaction.response.send_message(embed=e, file=f, ephemeral=True)


class BannerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        return users, cards_db

    # ── !banners ───────────────────────────────────────────────

    @commands.command(name="banners")
    async def banners_cmd(self, ctx: commands.Context) -> None:
        users, cards_db = self._load()
        banners = get_or_rotate_banners(cards_db)

        img = render_banners_image(banners, cards_db)
        f   = pil_to_discord_file(img, "banners.png")

        # mostrar pity del usuario
        uid   = str(ctx.author.id)
        ensure_user(users, uid)
        pity  = get_pity(users, uid)
        pg    = pity.get("pulls_since_gacha", 0)
        pm    = pity.get("pulls_since_4star",  0)

        desc = (
            f"**Tu pity actual:** {pg}/90 (carta gacha) • {pm}/10 (artículo 4★)\n\n"
            f"Usá `!ptira <id>` para 1 tirada — `!ptira10 <id>` para 10 tiradas\n"
            f"Cada tirada cuesta **{BANNER_PULL_COST}** monedas • x10: **{BANNER_PULL10_COST}** monedas"
        )
        e = discord.Embed(description=desc, color=0xff78dc).set_image(url="attachment://banners.png")
        await ctx.reply(embed=e, file=f, view=NextBannersView(cards_db))

    # ── !ptira <id> ───────────────────────────────────────────

    @commands.command(name="ptira")
    async def ptira_cmd(self, ctx: commands.Context, banner_id: str = "") -> None:
        await self._pull(ctx, banner_id, count=1)

    # ── !ptira10 <id> ─────────────────────────────────────────

    @commands.command(name="ptira10")
    async def ptira10_cmd(self, ctx: commands.Context, banner_id: str = "") -> None:
        await self._pull(ctx, banner_id, count=10)

    # ── !ppity ────────────────────────────────────────────────

    @commands.command(name="ppity")
    async def ppity_cmd(self, ctx: commands.Context) -> None:
        users, _ = self._load()
        uid      = str(ctx.author.id)
        ensure_user(users, uid)
        pity = get_pity(users, uid)
        pg   = pity.get("pulls_since_gacha", 0)
        pm   = pity.get("pulls_since_4star",  0)
        e = discord.Embed(
            title="🎰 Tu pity de banner",
            description=(
                f"**Carta gacha:** {pg} / 90 tiradas\n"
                f"**Artículo 4★:** {pm} / 10 tiradas\n\n"
                f"El pity es compartido entre todos los banners y no se resetea al cambiar."
            ),
            color=0xff78dc,
        )
        await ctx.reply(embed=e)

    # ── lógica interna ────────────────────────────────────────

    async def _pull(self, ctx: commands.Context, banner_id: str, count: int) -> None:
        if not banner_id:
            await ctx.reply(f"Especificá el ID del banner. Ej: `!ptira 1`")
            return

        users, cards_db = self._load()
        banner = get_banner(banner_id, cards_db)
        if not banner:
            await ctx.reply(f"No hay ningún banner activo con ID **{banner_id}**.")
            return
        uid   = str(ctx.author.id)
        ensure_user(users, uid)

        cost  = BANNER_PULL_COST * count
        gold  = int(users[uid].get("gold", 0))
        if gold < cost:
            await ctx.reply(f"💸 No tenés oro suficiente. Necesitás **{cost}** oro (tenés **{gold}**).")
            return

        users[uid]["gold"] = gold - cost

        # leer referencia al pity ANTES de tirar para garantizar que se guarde
        pity_ref = get_pity(users, uid)

        results = do_pulls(users, uid, banner, cards_db, count=count)
        apply_pull_results(users, uid, results, cards_db)

        users[uid]["gacha_pity"] = pity_ref   # garantiza que la referencia esté en el dict
        save_users(users)

        # imagen de resultados
        img = render_pull_result(results, cards_db, ctx.author.display_name)
        f   = pil_to_discord_file(img, "pull.png")

        pity = get_pity(users, uid)
        pg   = pity.get("pulls_since_gacha", 0)
        pm   = pity.get("pulls_since_4star",  0)

        # resumen en embed
        highlights = [r for r in results if r["type"] in ("gacha_card", "4star")]
        gold_total = sum(r["amount"] for r in results if r["type"] == "gold")

        lines = []
        for r in highlights:
            if r["type"] == "gacha_card":
                card_name = r.get("card") or r.get("name", "?")
                lines.append(f"✦ **GACHA** — {card_name} (*{r['collection']}*)")
            else:
                tipo = "Marco" if r["item_type"] == "frame" else "Fondo"
                lines.append(f"★ **{tipo}**: {r['name']}")
        if gold_total:
            lines.append(f"💰 Oro total: **+{gold_total}**")

        desc = "\n".join(lines) if lines else "Solo oro esta vez... ¡seguí intentando!"
        desc += f"\n\n*Pity: {pg}/90 carta • {pm}/10 artículo*"

        e = discord.Embed(
            title=f"🎰 Tiradas en Banner #{banner_id} — {banner['name']}",
            description=desc,
            color=0xff78dc,
        ).set_image(url="attachment://pull.png")

        await ctx.reply(embed=e, file=f)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BannerCog(bot))

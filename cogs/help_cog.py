from __future__ import annotations

import discord
from discord.ext import commands

from config import OWNER_ID


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="phelp")
    async def phelp_cmd(self, ctx: commands.Context) -> None:
        e = discord.Embed(title="📖 Comandos del bot", color=0x3498db, description=(
            "**Gacha & Cartas**\n"
            "`pgacha` — Abrir 5 cartas\n"
            "`pdrop` — Lanzar un drop público de cartas\n"
            "`pver [código]` — Ver una carta por código\n"
            "`pcartas [@usuario]` — Listar todas las instancias de cartas\n\n"
            "**Colección & Álbum**\n"
            "`palbums [@usuario]` — Álbum de todas las colecciones\n"
            "`palbum <serie> [@usuario]` — Ver una colección específica\n"
            "`pinv [@usuario]` — Inventario con estadísticas\n\n"
            "**Economía**\n"
            "`pdaily` — Recompensa diaria\n"
            "`pwork` — Trabajar por oro\n"
            "`pvender <código>` — Vender una carta por código\n"
            "`pvender rep [@usuario]` — Vender repetidas\n\n"
            "**Tienda & Compras**\n"
            "`pbuy` — Abrir tienda\n"
            "`psobres` — Ver sobres disponibles (aún no impl.)\n\n"
            "**Wishlist**\n"
            "`pwl` — Ver tu wishlist\n"
            "`pwladd <carta>` — Agregar a wishlist\n"
            "`pwlremove <carta>` — Quitar de wishlist\n\n"
            "**Casino**\n"
            "`pcasino` — Entrar al casino\n\n"
            "**Museo**\n"
            "`pmuseo [@usuario]` — Ver el museo\n"
            "`pmadd <código> <slot>` — Agregar carta al museo\n"
            "`pmremove <slot>` — Quitar carta del museo\n"
            "`pmclear` — Limpiar museo\n"
            "`pmset <fondo>` — Cambiar fondo del museo\n"
            "`pmarcos [@usuario]` — Ver marcos disponibles\n\n"
            "**Tokens**\n"
            "`ptokens` — Ver tus tokens\n"
            "`plu <carta>` — Lookup de cartas y tokens\n\n"
            "**Trade**\n"
            "`ptrade @usuario` — Iniciar intercambio\n"
        ))
        await ctx.reply(embed=e)

    @commands.command(name="padm")
    @commands.is_owner()
    async def padm_cmd(self, ctx: commands.Context) -> None:
        e = discord.Embed(title="🛠️ Comandos de admin", color=0xe74c3c, description=(
            "`givegold @user <amount>` — Dar oro\n"
            "`setgold @user <amount>` — Fijar oro\n"
            "`giveframe @user <frame_id>` — Dar marco\n"
            "`givepack @user <rarity> [cantidad]` — Dar sobre\n\n"
            "**Eventos**\n"
            "`eventshow` — Ver config de eventos\n"
            "`eventset <on/off>` — Activar/desactivar eventos\n"
            "`eventadd <col>` — Agregar colección activa\n"
            "`eventremove <col>` — Quitar colección activa\n"
            "`eventban <col>` — Banear colección\n"
            "`eventunban <col>` — Desbanear colección\n"
            "`eventclearbans` — Limpiar bans\n\n"
            "**Shop**\n"
            "`shopshow` — Ver config de tienda\n"
            "`shopset <on/off>` — Activar/desactivar tienda\n"
            "`shopadd <col>` — Agregar colección a tienda\n"
            "`shopremove <col>` — Quitar colección de tienda\n"
            "`shopclear` — Limpiar tienda\n"
        ))
        await ctx.reply(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))

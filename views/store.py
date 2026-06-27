from __future__ import annotations

from typing import List, Optional

import discord

from config import BUY_ONE_COST
from core.cards import (
    create_card_instance_from_meta, migrate_users_cards, normalize_cards, rarity_es,
)
from core.events import load_shop_collections
from core.frames import load_frames_catalog
from core.museum_bgs import load_museum_bg_catalog, get_user_owned_bgs, give_user_bg
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from rendering.cards import pil_to_discord_file, render_single_card_image
from views.common import ack, edit_interaction_message


# ─── Store ────────────────────────────────────────────────────────────────────

class StoreView(discord.ui.View):
    def __init__(self, *, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Esa tienda no es tuya 😅", ephemeral=True)
            return False
        return True

    def _gold(self) -> int:
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        ensure_user(users, str(self.user_id))
        return int(users[str(self.user_id)].get("gold", 0))

    def make_embed(self) -> discord.Embed:
        gold = self._gold()
        return discord.Embed(
            title="🏪 Tienda",
            description=(
                f"💰 Oro: **{gold}**\n\n"
                f"🃏 **Carta aleatoria** — **{BUY_ONE_COST}** oro *(de la tienda activa)*\n"
                "🖼️ **Marcos** — Cosméticos para tus cartas\n"
                "🏛️ **Fondos de museo** — Cambiá el fondo de tu museo\n\n"
                "Elegí qué querés comprar:"
            ),
            color=0xe67e22,
        )

    @discord.ui.button(label="🃏 Comprar carta", style=discord.ButtonStyle.primary)
    async def buy_card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid = str(self.user_id)
        ensure_user(users, uid)
        gold = int(users[uid].get("gold", 0))

        if gold < BUY_ONE_COST:
            await interaction.followup.send(f"No tenés suficiente oro. Necesitás **{BUY_ONE_COST}** 💰", ephemeral=True)
            return

        shop_collections = load_shop_collections(cards_db)
        if not shop_collections:
            await interaction.followup.send("La tienda no tiene colecciones activas.", ephemeral=True)
            return

        view = BuyOneView(user_id=self.user_id, shop_collections=shop_collections, cards_db=cards_db, gold=gold)
        e    = view.make_embed()
        await interaction.followup.send(embed=e, view=view, ephemeral=False)

    @discord.ui.button(label="🖼️ Marcos", style=discord.ButtonStyle.secondary)
    async def frames_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        catalog = load_frames_catalog()
        if not catalog:
            await interaction.followup.send("No hay marcos en la tienda aún.", ephemeral=True)
            return
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        ensure_user(users, str(self.user_id))
        gold = int(users[str(self.user_id)].get("gold", 0))
        view = FramesShopView(user_id=self.user_id, catalog=catalog, gold=gold)
        await interaction.followup.send(embed=view.make_embed(), view=view, ephemeral=False)

    @discord.ui.button(label="🏛️ Fondos de museo", style=discord.ButtonStyle.secondary)
    async def museum_bgs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        catalog = load_museum_bg_catalog()
        shop_catalog = {k: v for k, v in catalog.items() if v.get("shop")}
        if not shop_catalog:
            await interaction.followup.send("No hay fondos de museo en la tienda aún.", ephemeral=True)
            return
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(self.user_id)
        ensure_user(users, uid)
        gold  = int(users[uid].get("gold", 0))
        owned = get_user_owned_bgs(users, uid)
        view  = MuseumBgShopView(user_id=self.user_id, catalog=shop_catalog, gold=gold, owned=owned)
        await interaction.followup.send(embed=view.make_embed(), view=view)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()


# ─── BuyOne ───────────────────────────────────────────────────────────────────

class BuyOneSelect(discord.ui.Select):
    def __init__(self, *, user_id: int, shop_collections: List[str], cards_db: dict):
        options = [
            discord.SelectOption(label=c[:100], value=c)
            for c in sorted(shop_collections, key=lambda s: str(s).lower())
        ][:25]
        super().__init__(placeholder="Elegí una colección…", min_values=1, max_values=1, options=options)
        self.user_id         = user_id
        self.shop_collections = shop_collections
        self.cards_db        = cards_db

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_collection = self.values[0]
        await self.view.show_preview(interaction)


class BuyOneView(discord.ui.View):
    def __init__(self, *, user_id: int, shop_collections: List[str], cards_db: dict, gold: int):
        super().__init__(timeout=120)
        self.user_id            = user_id
        self.shop_collections   = shop_collections
        self.cards_db           = cards_db
        self.gold               = gold
        self.selected_collection: Optional[str] = None
        self.add_item(BuyOneSelect(user_id=user_id, shop_collections=shop_collections, cards_db=cards_db))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🃏 Comprar carta",
            description=f"💰 Oro: **{self.gold}** | Costo: **{BUY_ONE_COST}**\nElegí la colección de donde querés obtener una carta aleatoria.",
            color=0x3498db,
        )

    async def show_preview(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        col = self.selected_collection
        if not col:
            await edit_interaction_message(interaction, embed=self.make_embed(), view=self)
            return
        e = discord.Embed(
            title=f"🃏 Comprar carta de {col}",
            description=f"💰 Oro: **{self.gold}** | Costo: **{BUY_ONE_COST}**\nPresioná **Confirmar** para comprar.",
            color=0x3498db,
        )
        await edit_interaction_message(interaction, embed=e, view=self)

    @discord.ui.button(label="✅ Confirmar compra", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        col = self.selected_collection
        if not col:
            await interaction.followup.send("Elegí una colección primero.", ephemeral=True)
            return

        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid = str(self.user_id)
        ensure_user(users, uid)
        gold = int(users[uid].get("gold", 0))
        if gold < BUY_ONE_COST:
            await interaction.followup.send("No tenés suficiente oro 💸", ephemeral=True)
            return

        pool = [(n, d) for n, d in (cards_db.get(col) or {}).items() if d.get("img")]
        if not pool:
            await interaction.followup.send("Esa colección no tiene cartas válidas.", ephemeral=True)
            return

        import random
        name, _ = random.choice(pool)
        inst = create_card_instance_from_meta(col, name, cards_db, users)
        users[uid]["gold"] = gold - BUY_ONE_COST
        users[uid].setdefault("cards", []).append(inst)
        save_users(users)

        img = render_single_card_image(cards_db, inst)
        f   = pil_to_discord_file(img, "bought.png")
        e   = discord.Embed(
            title="✅ Compra realizada",
            description=(
                f"Obtuviste: **{name}** (*{col}*)\n"
                f"Rareza: **{rarity_es(inst['rarity'])}** | Código: `{inst['code']}`\n"
                f"Valor: **P{inst['value']}** | Oro restante: **{users[uid]['gold']}**"
            ),
            color=0x2ecc71,
        ).set_image(url="attachment://bought.png")

        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, attachments=[f], view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=discord.Embed(title="Compra cancelada", color=0x95a5a6), view=self)
        self.stop()


# ─── FramesShop ───────────────────────────────────────────────────────────────

class FramesBuySelect(discord.ui.Select):
    def __init__(self, *, user_id: int, catalog: dict):
        options = [
            discord.SelectOption(
                label=f"[ID {fid}] {meta['name']}"[:100],
                description=f"Precio: {meta['price']} oro"[:100],
                value=str(fid),
            )
            for fid, meta in catalog.items() if meta.get("shop")
        ][:25]
        super().__init__(placeholder="Elegí un marco…", min_values=1, max_values=1, options=options)
        self.user_id = user_id
        self.catalog = catalog

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_frame_id = int(self.values[0])
        await self.view.show_selected(interaction)


class FramesShopView(discord.ui.View):
    def __init__(self, *, user_id: int, catalog: dict, gold: int):
        super().__init__(timeout=120)
        self.user_id           = user_id
        self.catalog           = catalog
        self.gold              = gold
        self.selected_frame_id: Optional[int] = None
        self.add_item(FramesBuySelect(user_id=user_id, catalog=catalog))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🖼️ Marcos disponibles",
            description=f"💰 Oro: **{self.gold}**\nElegí un marco de la lista.",
            color=0x9b59b6,
        )

    async def show_selected(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        fid  = self.selected_frame_id
        meta = self.catalog.get(fid) if fid else None
        if not meta:
            await edit_interaction_message(interaction, embed=self.make_embed(), view=self)
            return
        e = discord.Embed(
            title=f"🖼️ Marco: {meta['name']}",
            description=f"Precio: **{meta['price']}** oro\n💰 Oro: **{self.gold}**\n¿Comprás este marco?",
            color=0x9b59b6,
        )
        await edit_interaction_message(interaction, embed=e, view=self)

    @discord.ui.button(label="✅ Comprar marco", style=discord.ButtonStyle.success)
    async def buy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        fid  = self.selected_frame_id
        meta = self.catalog.get(fid) if fid else None
        if not meta:
            await interaction.followup.send("Elegí un marco primero.", ephemeral=True)
            return

        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(self.user_id)
        ensure_user(users, uid)
        gold = int(users[uid].get("gold", 0))
        price = int(meta.get("price", 0))

        if gold < price:
            await interaction.followup.send("No tenés oro suficiente 💸", ephemeral=True)
            return

        users[uid]["gold"] = gold - price
        users[uid].setdefault("frames", [])
        if fid not in users[uid]["frames"]:
            users[uid]["frames"].append(fid)
        save_users(users)

        e = discord.Embed(
            title="✅ Marco comprado",
            description=f"Compraste el marco **{meta['name']}** (ID {fid})\nOro restante: **{users[uid]['gold']}**",
            color=0x2ecc71,
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel_btn_frames(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=discord.Embed(title="Compra cancelada", color=0x95a5a6), view=self)
        self.stop()


# ─── MuseumBgShop ─────────────────────────────────────────────────────────────

class MuseumBgBuySelect(discord.ui.Select):
    def __init__(self, *, user_id: int, catalog: dict, owned: list):
        self._owned_strs = [str(o) for o in owned]
        options = []
        for bg_id, meta in catalog.items():
            already = str(bg_id) in self._owned_strs
            label   = f"{'✅ ' if already else ''}{meta['name']} — {meta['price']} oro"
            options.append(discord.SelectOption(label=label[:100], value=str(bg_id)))
        super().__init__(placeholder="Elegí un fondo…", options=options[:25])
        self.user_id = user_id
        self.catalog = catalog

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_bg_id = self.values[0]
        await self.view.show_selected(interaction)


class MuseumBgShopView(discord.ui.View):
    def __init__(self, *, user_id: int, catalog: dict, gold: int, owned: list):
        super().__init__(timeout=120)
        self.user_id        = user_id
        self.catalog        = catalog
        self.gold           = gold
        self.owned          = owned
        self.selected_bg_id: Optional[str] = None
        self.add_item(MuseumBgBuySelect(user_id=user_id, catalog=catalog, owned=owned))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        owned_strs = [str(o) for o in self.owned]
        lines = []
        for bg_id, meta in self.catalog.items():
            tick       = "✅" if str(bg_id) in owned_strs else "⬜"
            museo_num  = meta.get("museum", 1)
            museo_tag  = f"Museo {'I' * museo_num}" if museo_num <= 3 else f"Museo {museo_num}"
            lines.append(f"{tick} **{meta['name']}** — {meta['price']} oro *(para {museo_tag})*")
        return discord.Embed(
            title="🏛️ Fondos de museo",
            description=f"💰 Oro: **{self.gold}**\n\n" + "\n".join(lines),
            color=0x2c3e50,
        )

    async def show_selected(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        bid  = self.selected_bg_id
        meta = self.catalog.get(bid) if bid else None
        if not meta:
            return
        already = str(bid) in [str(o) for o in self.owned]
        museo_num = meta.get("museum", 1)
        museo_tag = f"Museo {'I' * museo_num}" if museo_num <= 3 else f"Museo {museo_num}"
        desc = (
            f"**{meta['name']}** *(para {museo_tag})*\n"
            f"Precio: **{meta['price']}** oro\n💰 Oro tuyo: **{self.gold}**\n\n"
            + ("✅ Ya tenés este fondo." if already else "¿Querés comprarlo?")
        )
        e = discord.Embed(title="🏛️ Vista previa del fondo", description=desc, color=0x2c3e50)

        # adjuntar imagen de preview si existe
        import os
        from config import BASE_DIR
        img_path = os.path.join(BASE_DIR, "images", meta.get("img", ""))
        attachments = []
        if os.path.isfile(img_path):
            ext      = os.path.splitext(img_path)[1] or ".png"
            filename = f"bg_preview{ext}"
            e.set_image(url=f"attachment://{filename}")
            attachments = [discord.File(img_path, filename=filename)]

        await edit_interaction_message(interaction, embed=e, attachments=attachments, view=self)

    @discord.ui.button(label="✅ Comprar fondo", style=discord.ButtonStyle.success)
    async def buy_bg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        bid  = self.selected_bg_id
        meta = self.catalog.get(bid) if bid else None
        if not meta:
            await interaction.followup.send("Elegí un fondo primero.", ephemeral=True)
            return

        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(self.user_id)
        ensure_user(users, uid)

        if str(bid) in [str(o) for o in get_user_owned_bgs(users, uid)]:
            await interaction.followup.send("Ya tenés ese fondo.", ephemeral=True)
            return

        gold  = int(users[uid].get("gold", 0))
        price = int(meta.get("price", 0))
        if gold < price:
            await interaction.followup.send("No tenés oro suficiente 💸", ephemeral=True)
            return

        users[uid]["gold"] = gold - price
        give_user_bg(users, uid, str(bid))
        save_users(users)

        e = discord.Embed(
            title="✅ Fondo comprado",
            description=(
                f"Compraste el fondo **{meta['name']}**.\n"
                f"Oro restante: **{users[uid]['gold']}**\n\n"
                f"Usá `!pmset custom:{bid}` para activarlo en tu museo."
            ),
            color=0x2ecc71,
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel_bg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=discord.Embed(title="Compra cancelada", color=0x95a5a6), view=self)
        self.stop()

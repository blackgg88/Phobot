from __future__ import annotations

from typing import Optional

import discord

from core.cards import migrate_users_cards, normalize_cards
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users, user_owned_pairs
from rendering.album import build_collection_page_image, collection_progress
from rendering.cards import pil_to_discord_file
from views.common import ack, edit_interaction_message


class ProgressPagerView(discord.ui.View):
    """Shows progress across all collections, paginated."""

    def __init__(self, *, viewer_id: int, target_user_id: str, cards_db, owned_set):
        super().__init__(timeout=180)
        self.viewer_id      = viewer_id
        self.target_user_id = target_user_id
        self.cards_db       = cards_db
        self.owned_set      = owned_set
        self.collection_list = sorted(cards_db.keys(), key=lambda s: str(s).lower())
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed_and_file(self):
        name             = self.collection_list[self.index]
        owned, total, pct = collection_progress(name, self.owned_set, self.cards_db)
        img, tp           = build_collection_page_image(name, self.owned_set, self.cards_db, page=0)
        f                 = pil_to_discord_file(img, "prog.png")
        e = discord.Embed(
            title=f"📊 Progreso — {name}",
            description=(
                f"Completado: **{owned}/{total} ({pct}%)**\n"
                f"Serie {self.index + 1}/{len(self.collection_list)}"
            ),
            color=0x1abc9c,
        ).set_image(url="attachment://prog.png")
        return e, f

    async def refresh(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        e, f = self.make_embed_and_file()
        await edit_interaction_message(interaction, embed=e, attachments=[f], view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.collection_list)
        await self.refresh(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def nxt(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.collection_list)
        await self.refresh(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()


class InventoryView(discord.ui.View):
    """Top-level user inventory panel."""

    def __init__(self, *, viewer_id: int, target_user_id: str):
        super().__init__(timeout=180)
        self.viewer_id      = viewer_id
        self.target_user_id = target_user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Ese inventario no es tuyo 😅", ephemeral=True)
            return False
        return True

    def _load(self):
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, self.target_user_id)
        return users, cards_db

    def make_embed(self, users: dict, cards_db: dict) -> discord.Embed:
        uid  = self.target_user_id
        u    = users[uid]
        cards = u.get("cards", [])
        gold  = u.get("gold", 0)
        owned_set = user_owned_pairs(cards)

        lines = [
            f"💰 Oro: **{gold}**",
            f"🃏 Cartas (instancias): **{len(cards)}**",
            f"🎴 Únicas: **{len(owned_set)}**",
        ]
        packs = u.get("packs", {})
        pack_lines = [f"  • {r}: x{packs.get(r, 0)}" for r in ["common", "rare", "epic", "legendary", "mythic"] if packs.get(r, 0) > 0]
        if pack_lines:
            lines.append("📦 Sobres:")
            lines.extend(pack_lines)

        coll_lines = []
        for col in sorted(cards_db.keys(), key=lambda s: str(s).lower()):
            owned, total, pct = collection_progress(col, owned_set, cards_db)
            coll_lines.append(f"  • {col}: {owned}/{total} ({pct}%)")
        if coll_lines:
            lines.append("📚 Colecciones:")
            lines.extend(coll_lines[:10])
            if len(coll_lines) > 10:
                lines.append(f"  …y {len(coll_lines) - 10} más")

        return discord.Embed(
            title="📂 Inventario",
            description="\n".join(lines),
            color=0x3498db,
        )

    @discord.ui.button(label="📊 Progreso por serie", style=discord.ButtonStyle.primary)
    async def progress_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users, cards_db = self._load()
        owned_set = user_owned_pairs(users[self.target_user_id].get("cards", []))
        view = ProgressPagerView(
            viewer_id=self.viewer_id,
            target_user_id=self.target_user_id,
            cards_db=cards_db,
            owned_set=owned_set,
        )
        e, f = view.make_embed_and_file()
        await interaction.followup.send(embed=e, file=f, view=view, ephemeral=False)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

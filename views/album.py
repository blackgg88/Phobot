from __future__ import annotations

from math import ceil
from typing import Set, Tuple

import discord

from core.cards import migrate_users_cards
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users, user_owned_pairs
from rendering.album import build_collection_page_image, collection_progress
from rendering.cards import pil_to_discord_file
from views.common import ack, edit_interaction_message


class CollectionPager(discord.ui.View):
    def __init__(self, *, viewer_id: int, target_user_id: str, collection_names,
                 cards_db, owned_set: Set[Tuple[str, str]]):
        super().__init__(timeout=180)
        self.viewer_id      = viewer_id
        self.target_user_id = target_user_id
        self.collection_names = sorted(list(collection_names), key=lambda s: str(s).lower())
        self.cards_db       = cards_db
        self.owned_set      = owned_set
        self.index          = 0
        self.per_page_preview = 12

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Ese álbum no es tuyo 😅", ephemeral=True)
            return False
        return True

    def current_name(self) -> str:
        return self.collection_names[self.index]

    def make_embed(self, preview_pages: int = 1) -> discord.Embed:
        name = self.current_name()
        owned, total, pct = collection_progress(name, self.owned_set, self.cards_db)
        return discord.Embed(
            title=f"📚 Álbum — {name}",
            description=(
                f"Completado: **{owned}/{total} ({pct}%)**\n"
                f"Álbumes: **{self.index + 1}/{len(self.collection_names)}**\n"
                f"Vista previa: **1/{max(1, preview_pages)}** (12 por página)\n"
                f"Tip: `palbum {name}` para ver todas las páginas."
            ),
            color=0x2ecc71,
        ).set_image(url="attachment://album.png")

    def build_file(self):
        img, total_pages = build_collection_page_image(
            self.current_name(), self.owned_set, self.cards_db,
            page=0, per_page=self.per_page_preview,
        )
        return pil_to_discord_file(img, "album.png"), total_pages

    async def update(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        try:
            f, tp = self.build_file()
            embed = self.make_embed(preview_pages=tp)
            await edit_interaction_message(interaction, embed=embed, attachments=[f], view=self)
        except Exception as e:
            try:
                embed = discord.Embed(title="💥 Error", description=f"`{type(e).__name__}`", color=0xE74C3C)
                await edit_interaction_message(interaction, embed=embed, view=self)
            except Exception:
                pass

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.collection_names)
        await self.update(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.collection_names)
        await self.update(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()


class SingleCollectionPager(discord.ui.View):
    def __init__(self, *, viewer_id: int, target_user_id: str, collection_name: str,
                 cards_db, owned_set: Set[Tuple[str, str]]):
        super().__init__(timeout=180)
        self.viewer_id       = viewer_id
        self.target_user_id  = target_user_id
        self.collection_name = collection_name
        self.cards_db        = cards_db
        self.owned_set       = owned_set
        self.page            = 0
        self.per_page        = 12
        self.total_pages     = 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Ese álbum no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        owned, total, pct = collection_progress(self.collection_name, self.owned_set, self.cards_db)
        return discord.Embed(
            title=f"📌 Colección — {self.collection_name}",
            description=(
                f"Completado: **{owned}/{total} ({pct}%)**\n"
                f"Página: **{self.page + 1}/{self.total_pages}** (12 por página)"
            ),
            color=0x2ecc71,
        ).set_image(url="attachment://album.png")

    def build_file(self):
        img, total_pages = build_collection_page_image(
            self.collection_name, self.owned_set, self.cards_db,
            page=self.page, per_page=self.per_page,
        )
        self.total_pages = total_pages
        return pil_to_discord_file(img, "album.png")

    async def refresh(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        from core.cards import normalize_cards
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        ensure_user(users, self.target_user_id)
        self.cards_db   = cards_db
        self.owned_set  = user_owned_pairs(users[self.target_user_id].get("cards", []))
        self.total_pages = max(1, ceil(len(list(self.cards_db[self.collection_name].keys())) / self.per_page))
        if self.page >= self.total_pages:
            self.page = self.total_pages - 1

        f = self.build_file()
        await edit_interaction_message(interaction, embed=self.make_embed(), attachments=[f], view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % self.total_pages
        await self.refresh(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % self.total_pages
        await self.refresh(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

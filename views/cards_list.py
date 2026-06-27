from __future__ import annotations

from math import ceil
from typing import List

import discord

from core.cards import migrate_users_cards, normalize_cards, rarity_es
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from views.common import ack, edit_interaction_message


class CardsSortSelect(discord.ui.Select):
    def __init__(self, viewer_id: int):
        options = [
            discord.SelectOption(label="Orden de obtención", value="order"),
            discord.SelectOption(label="Alfabético (A-Z)",   value="alpha"),
            discord.SelectOption(label="Por serie/colección", value="series"),
            discord.SelectOption(label="Por valor (mejor→peor)", value="value"),
        ]
        super().__init__(placeholder="Ordenar…", min_values=1, max_values=1, options=options)
        self.viewer_id = viewer_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return
        self.view.sort_mode = self.values[0]
        self.view.page = 0
        await self.view.refresh(interaction)


class CardsListView(discord.ui.View):
    def __init__(self, *, viewer_id: int):
        super().__init__(timeout=240)
        self.viewer_id = viewer_id
        self.page      = 0
        self.per_page  = 15
        self.sort_mode = "order"
        self.add_item(CardsSortSelect(viewer_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Ese listado no es tuyo 😅", ephemeral=True)
            return False
        return True

    def _sorted_cards(self, cards: List[dict]) -> List[dict]:
        if self.sort_mode == "alpha":
            return sorted(cards, key=lambda x: (str(x.get("name", "")).lower(), str(x.get("collection", "")).lower()))
        if self.sort_mode == "series":
            return sorted(cards, key=lambda x: (str(x.get("collection", "")).lower(), str(x.get("name", "")).lower()))
        if self.sort_mode == "value":
            return sorted(cards, key=lambda x: int(x.get("value", 999999)))
        return list(reversed(cards))

    def build_embed(self, cards: List[dict]) -> discord.Embed:
        total        = len(cards)
        sorted_cards = self._sorted_cards(cards)
        total_pages  = max(1, ceil(total / self.per_page))
        self.page    = max(0, min(self.page, total_pages - 1))

        chunk = sorted_cards[self.page * self.per_page : (self.page + 1) * self.per_page]
        lines = []
        for c in chunk:
            gen = c.get("gen")
            gen_tag = f"G·{gen}" if gen is not None else "G·???"
            lines.append(
                f"`{c.get('code')}` — **{c.get('name')}** (*{c.get('collection')}*) — **{gen_tag}** — {rarity_es(c.get('rarity'))}"
            )
        mode_map = {"order": "obtención", "alpha": "A-Z", "series": "serie", "value": "valor"}
        e = discord.Embed(
            title="🗂️ Tus cartas (instancias)",
            description="\n".join(lines) or "No tenés cartas todavía.",
            color=0x3498db,
        )
        e.set_footer(text=f"Orden: {mode_map.get(self.sort_mode, self.sort_mode)} | Página {self.page+1}/{max(1, ceil(total/self.per_page))} | Total: {total}")
        return e

    async def refresh(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, str(self.viewer_id))
        cards = users[str(self.viewer_id)].get("cards", [])
        await edit_interaction_message(interaction, embed=self.build_embed(cards), view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self.refresh(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.refresh(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

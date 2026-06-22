from __future__ import annotations

from math import ceil

import discord

from core.tokens import sorted_tokens
from views.common import ack, edit_interaction_message


_SORT_OPTIONS = [
    discord.SelectOption(label="Últimos agregados",   value="ultimos"),
    discord.SelectOption(label="Primeros agregados",  value="primeros"),
    discord.SelectOption(label="Por serie",           value="serie"),
    discord.SelectOption(label="Alfabético (A-Z)",    value="az"),
]


class TokenSortSelect(discord.ui.Select):
    def __init__(self, *, user_id: int):
        super().__init__(placeholder="Ordenar…", min_values=1, max_values=1, options=_SORT_OPTIONS)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return
        self.view.sort_mode = self.values[0]
        self.view.page = 0
        await self.view.refresh(interaction)


class TokensListView(discord.ui.View):
    def __init__(self, *, user_id: int, tokens: list, sort_mode: str = "ultimos"):
        super().__init__(timeout=180)
        self.user_id  = user_id
        self.tokens   = tokens
        self.sort_mode = sort_mode
        self.page     = 0
        self.per_page = 15
        self.add_item(TokenSortSelect(user_id=user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        ordered  = sorted_tokens(self.tokens, self.sort_mode)
        total    = len(ordered)
        total_pages = max(1, ceil(total / self.per_page))
        self.page   = max(0, min(self.page, total_pages - 1))
        chunk = ordered[self.page * self.per_page : (self.page + 1) * self.per_page]

        lines = [
            f"`{t.get('code')}` — **{t.get('name')}** (*{t.get('collection')}*)"
            for t in chunk
        ]
        e = discord.Embed(
            title="🎭 Tokens",
            description="\n".join(lines) or "No tenés tokens.",
            color=0xe74c3c,
        )
        e.set_footer(text=f"Orden: {self.sort_mode} | Página {self.page+1}/{total_pages} | Total: {total}")
        return e

    async def refresh(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        await edit_interaction_message(interaction, embed=self.make_embed(), view=self)

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

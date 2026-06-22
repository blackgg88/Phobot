from __future__ import annotations

import asyncio
import time
from typing import List, Optional

import discord

from config import DROP_PRIORITY_SECONDS, DROP_TAKE_COOLDOWN
from core.cards import create_card_instance_from_meta, migrate_users_cards, normalize_cards, rarity_es
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from views.common import ack, edit_interaction_message


class DropView(discord.ui.View):
    def __init__(self, *, drop_user_id: int, cards: List[dict], drop_time: float):
        super().__init__(timeout=120)
        self.drop_user_id = drop_user_id
        self.cards        = cards
        self.drop_time    = drop_time
        self.lock         = asyncio.Lock()
        self.taken_by: Optional[int] = None
        self.taken_by_name: str = ""

        for i, c in enumerate(cards):
            label = f"Agarrar {c.get('name', f'carta {i+1}')}"
            btn   = discord.ui.Button(label=label[:80], style=discord.ButtonStyle.success, custom_id=f"drop_take_{i}")
            async def _cb(interaction: discord.Interaction, idx=i):
                await self.take_card(interaction, idx)
            btn.callback = _cb
            self.add_item(btn)

    async def take_card(self, interaction: discord.Interaction, card_idx: int) -> None:
        uid = str(interaction.user.id)

        async with self.lock:
            now = time.time()
            is_dropper = interaction.user.id == self.drop_user_id
            in_priority = (now - self.drop_time) < DROP_PRIORITY_SECONDS

            if in_priority and not is_dropper:
                remaining = int(DROP_PRIORITY_SECONDS - (now - self.drop_time)) + 1
                await interaction.response.send_message(
                    f"⏳ El que droppeó tiene prioridad por {remaining}s más.", ephemeral=True
                )
                return

            users_path, _, _ = get_paths()
            users = load_json(users_path, {})
            ensure_user(users, uid)

            last_take = users[uid].get("last_drop_take", 0)
            if (now - last_take) < DROP_TAKE_COOLDOWN:
                rem = int(DROP_TAKE_COOLDOWN - (now - last_take))
                m, s = divmod(rem, 60)
                await interaction.response.send_message(f"⏰ Cooldown: {m}m {s}s.", ephemeral=True)
                return

            card = self.cards[card_idx]

            from core.cards import normalize_cards, migrate_users_cards
            _, cards_path, _ = get_paths()
            cards_db = normalize_cards(load_json(cards_path, {}))
            if migrate_users_cards(users, cards_db):
                save_users(users)

            inst = create_card_instance_from_meta(card.get("collection"), card.get("name"), cards_db, users)
            users[uid].setdefault("cards", []).append(inst)
            users[uid]["last_drop_take"] = now
            save_users(users)

            self.taken_by      = interaction.user.id
            self.taken_by_name = str(interaction.user.display_name)

            for child in self.children:
                child.disabled = True

        e = discord.Embed(
            title="✅ Carta tomada",
            description=(
                f"{interaction.user.mention} tomó **{card.get('name')}** (*{card.get('collection')}*)\n"
                f"Rareza: **{rarity_es(inst.get('rarity', 'common'))}** | Código: `{inst['code']}`\nValor: **P{inst['value']}**"
            ),
            color=0x2ecc71,
        )
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=e, view=self, attachments=[])
            else:
                await interaction.response.edit_message(embed=e, view=self, attachments=[])
        except Exception:
            try:
                await interaction.message.edit(embed=e, view=self, attachments=[])
            except Exception:
                pass
        self.stop()

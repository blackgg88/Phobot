from __future__ import annotations

import asyncio
import time
from typing import List, Optional

import discord

from config import DROP_PRIORITY_SECONDS, DROP_TAKE_COOLDOWN
from core.cards import create_card_instance_from_meta, migrate_users_cards, normalize_cards, rarity_es
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users


RARITY_EMOJI = {
    "common":    "⬜",
    "rare":      "🔷",
    "epic":      "🟣",
    "legendary": "⭐",
    "mythic":    "🔴",
}


class DropView(discord.ui.View):
    def __init__(self, *, drop_user_id: int, cards: List[dict], drop_time: float):
        super().__init__(timeout=120)
        self.drop_user_id = drop_user_id
        self.cards        = cards
        self.drop_time    = drop_time
        self.lock         = asyncio.Lock()
        # one slot per card: None = unclaimed, int = user_id who claimed it
        self.claimed: List[Optional[int]] = [None] * len(cards)
        self.claimed_names: List[str]     = [""] * len(cards)

        for i, c in enumerate(cards):
            name_label = c.get("name", f"Carta {i+1}")[:40]
            btn = discord.ui.Button(
                label=f"❤  {name_label}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"drop_take_{i}",
                row=0,
            )
            async def _cb(interaction: discord.Interaction, idx=i):
                await self.take_card(interaction, idx)
            btn.callback = _cb
            self.add_item(btn)

    def _all_claimed(self) -> bool:
        return all(c is not None for c in self.claimed)

    async def take_card(self, interaction: discord.Interaction, card_idx: int) -> None:
        uid = str(interaction.user.id)

        async with self.lock:
            now = time.time()
            is_dropper  = interaction.user.id == self.drop_user_id
            in_priority = (now - self.drop_time) < DROP_PRIORITY_SECONDS

            if in_priority and not is_dropper:
                remaining = int(DROP_PRIORITY_SECONDS - (now - self.drop_time)) + 1
                await interaction.response.send_message(
                    f"⏳ El que droppeó tiene prioridad por {remaining}s más.", ephemeral=True
                )
                return

            if self.claimed[card_idx] is not None:
                await interaction.response.send_message(
                    "❌ Esa carta ya fue tomada.", ephemeral=True
                )
                return

            users_path, cards_path, _ = get_paths()
            users    = load_json(users_path, {})
            cards_db = normalize_cards(load_json(cards_path, {}))
            ensure_user(users, uid)

            last_take = users[uid].get("last_drop_take", 0)
            if (now - last_take) < DROP_TAKE_COOLDOWN:
                rem = int(DROP_TAKE_COOLDOWN - (now - last_take))
                m, s = divmod(rem, 60)
                await interaction.response.send_message(f"⏰ Cooldown: {m}m {s}s.", ephemeral=True)
                return

            if migrate_users_cards(users, cards_db):
                save_users(users)

            card = self.cards[card_idx]
            inst = create_card_instance_from_meta(card.get("collection"), card.get("name"), cards_db, users)
            users[uid].setdefault("cards", []).append(inst)
            users[uid]["last_drop_take"] = now
            save_users(users)

            self.claimed[card_idx]       = interaction.user.id
            self.claimed_names[card_idx] = str(interaction.user.display_name)

            # disable only the button for this card
            for child in self.children:
                if getattr(child, "custom_id", None) == f"drop_take_{card_idx}":
                    child.disabled = True
                    child.label    = f"✅  {card.get('name', '')}"[:80]
                    child.style    = discord.ButtonStyle.success
                    break

        rarity_label = rarity_es(inst.get("rarity", "common"))
        reply_text = (
            f"✅ **{interaction.user.display_name}** agarró **{card.get('name')}** "
            f"(*{card.get('collection')}*) — {rarity_label} | `{inst['code']}` | P{inst['value']}"
        )

        try:
            await interaction.response.send_message(reply_text)
        except Exception:
            try:
                await interaction.channel.send(reply_text)
            except Exception:
                pass

        # update view on the original drop message
        try:
            if self._all_claimed():
                for child in self.children:
                    child.disabled = True
                self.stop()
            await interaction.message.edit(view=self)
        except Exception:
            pass

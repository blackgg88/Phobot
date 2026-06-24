from __future__ import annotations

import asyncio
import random
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

_SUITS = ["♠", "♥", "♦", "♣"]


class SingleDropView(discord.ui.View):
    """One button for one card — shown below each individual card image."""

    def __init__(self, *, drop_user_id: int, card: dict, drop_time: float):
        super().__init__(timeout=120)
        self.drop_user_id = drop_user_id
        self.card         = card
        self.drop_time    = drop_time
        self.claimed_by: Optional[int] = None
        self.lock = asyncio.Lock()

        suit  = random.choice(_SUITS)
        label = f"{suit}  {card.get('name', 'Carta')}"[:80]
        btn   = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.secondary,
            custom_id="drop_take",
            row=0,
        )
        btn.callback = self._take
        self.add_item(btn)

    async def _take(self, interaction: discord.Interaction) -> None:
        uid = str(interaction.user.id)

        async with self.lock:
            now        = time.time()
            is_dropper = interaction.user.id == self.drop_user_id
            in_priority = (now - self.drop_time) < DROP_PRIORITY_SECONDS

            if in_priority and not is_dropper:
                remaining = int(DROP_PRIORITY_SECONDS - (now - self.drop_time)) + 1
                await interaction.response.send_message(
                    f"⏳ El que droppeó tiene prioridad por {remaining}s más.", ephemeral=True
                )
                return

            if self.claimed_by is not None:
                await interaction.response.send_message("❌ Esa carta ya fue tomada.", ephemeral=True)
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

            inst = create_card_instance_from_meta(
                self.card.get("collection"), self.card.get("name"), cards_db, users
            )
            users[uid].setdefault("cards", []).append(inst)
            users[uid]["last_drop_take"] = now

            from core.missions import progress as mission_progress
            claim_completed = mission_progress(users, uid, "claims", 1)
            save_users(users)

            self.claimed_by = interaction.user.id
            for child in self.children:
                child.disabled = True
                child.label    = f"✅  {self.card.get('name', '')}"[:80]
                child.style    = discord.ButtonStyle.success
            self.stop()

        for label, reward in claim_completed:
            users_path2, _, _ = get_paths()
            users2 = load_json(users_path2, {})
            users2[uid]["gold"] = int(users2[uid].get("gold", 0)) + reward
            save_users(users2)
            try:
                from core.bot_channel import get_bot_channel
                ch = (get_bot_channel(interaction.guild) if interaction.guild else None) or interaction.channel
                await ch.send(
                    f"✅ {interaction.user.mention} completó la misión **{label}** — **+{reward}** oro 💰"
                )
            except Exception:
                pass

        rarity_label = rarity_es(inst.get("rarity", "common"))
        reply_text = (
            f"✅ **{interaction.user.display_name}** agarró **{self.card.get('name')}** "
            f"(*{self.card.get('collection')}*) — {rarity_label} | `{inst['code']}` | P{inst['value']}"
        )

        try:
            await interaction.response.send_message(reply_text)
        except Exception:
            try:
                await interaction.channel.send(reply_text)
            except Exception:
                pass

        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass


# ── Multi-card view: 3 images sent together, 3 buttons in one row ─────────────

class MultiDropView(discord.ui.View):
    """One button per card in a single row, each button claims only its card."""

    def __init__(self, *, drop_user_id: int, cards: List[dict], drop_time: float):
        super().__init__(timeout=120)
        self.drop_user_id = drop_user_id
        self.cards        = cards
        self.drop_time    = drop_time
        self.lock         = asyncio.Lock()
        self.claimed: List[Optional[int]] = [None] * len(cards)

        for i, c in enumerate(cards):
            suit  = random.choice(_SUITS)
            label = f"{suit}  {c.get('name', f'Carta {i+1}')}"[:80]
            btn   = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"mdrop_{i}",
                row=0,
            )
            async def _cb(interaction: discord.Interaction, idx=i):
                await self._take(interaction, idx)
            btn.callback = _cb
            self.add_item(btn)

    async def _take(self, interaction: discord.Interaction, card_idx: int) -> None:
        uid = str(interaction.user.id)

        async with self.lock:
            now        = time.time()
            is_dropper = interaction.user.id == self.drop_user_id
            in_priority = (now - self.drop_time) < DROP_PRIORITY_SECONDS

            if in_priority and not is_dropper:
                remaining = int(DROP_PRIORITY_SECONDS - (now - self.drop_time)) + 1
                await interaction.response.send_message(
                    f"⏳ El que droppeó tiene prioridad por {remaining}s más.", ephemeral=True
                )
                return

            if self.claimed[card_idx] is not None:
                await interaction.response.send_message("❌ Esa carta ya fue tomada.", ephemeral=True)
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

            from core.missions import progress as mission_progress
            claim_completed = mission_progress(users, uid, "claims", 1)
            save_users(users)

            self.claimed[card_idx] = interaction.user.id
            # disable ALL buttons after claim
            for child in self.children:
                cid = getattr(child, "custom_id", None)
                if cid == f"mdrop_{card_idx}":
                    child.disabled = True
                    child.label    = f"✅  {card.get('name', '')}"[:80]
                    child.style    = discord.ButtonStyle.success
                else:
                    child.disabled = True

        for label, reward in claim_completed:
            users_path2, _, _ = get_paths()
            users2 = load_json(users_path2, {})
            users2[uid]["gold"] = int(users2[uid].get("gold", 0)) + reward
            save_users(users2)
            try:
                from core.bot_channel import get_bot_channel
                ch = (get_bot_channel(interaction.guild) if interaction.guild else None) or interaction.channel
                await ch.send(
                    f"✅ {interaction.user.mention} completó la misión **{label}** — **+{reward}** oro 💰"
                )
            except Exception:
                pass

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

        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass


# ── Legacy combined view (kept for backwards compat) ──────────────────────────

class DropView(discord.ui.View):
    def __init__(self, *, drop_user_id: int, cards: List[dict], drop_time: float):
        super().__init__(timeout=120)
        self.drop_user_id = drop_user_id
        self.cards        = cards
        self.drop_time    = drop_time
        self.lock         = asyncio.Lock()
        self.claimed: List[Optional[int]] = [None] * len(cards)
        self.claimed_names: List[str]     = [""] * len(cards)

        for i, c in enumerate(cards):
            name_label = c.get("name", f"Carta {i+1}")[:40]
            suit = random.choice(_SUITS)
            btn = discord.ui.Button(
                label=f"{suit}  {name_label}",
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
                await interaction.response.send_message("❌ Esa carta ya fue tomada.", ephemeral=True)
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
            from core.missions import progress as mission_progress
            claim_completed = mission_progress(users, uid, "claims", 1)
            save_users(users)

            self.claimed[card_idx]       = interaction.user.id
            self.claimed_names[card_idx] = str(interaction.user.display_name)

            for child in self.children:
                cid = getattr(child, "custom_id", None)
                if cid == f"drop_take_{card_idx}":
                    child.disabled = True
                    child.label    = f"✅  {card.get('name', '')}"[:80]
                    child.style    = discord.ButtonStyle.success
                else:
                    child.disabled = True

        for label, reward in claim_completed:
            users_path2, _, _ = get_paths()
            users2 = load_json(users_path2, {})
            users2[uid]["gold"] = int(users2[uid].get("gold", 0)) + reward
            save_users(users2)
            try:
                from core.bot_channel import get_bot_channel
                ch = (get_bot_channel(interaction.guild) if interaction.guild else None) or interaction.channel
                await ch.send(
                    f"✅ {interaction.user.mention} completó la misión **{label}** — **+{reward}** oro 💰"
                )
            except Exception:
                pass

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

        try:
            if self._all_claimed():
                for child in self.children:
                    child.disabled = True
                self.stop()
            await interaction.message.edit(view=self)
        except Exception:
            pass

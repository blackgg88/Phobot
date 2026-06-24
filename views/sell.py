from __future__ import annotations

from typing import List, Optional

import discord

from config import SELL_VALUES
from core.cards import migrate_users_cards, normalize_cards, rarity_es, rarity_from_cards_db
from core.storage import get_paths, load_json
from core.users import (
    counts_by_char, ensure_user, remove_all_extras_instances,
    remove_one_extra_instance, save_users,
)
from rendering.cards import pil_to_discord_file, render_single_card_image
from views.common import ack, edit_interaction_message


class SellConfirmView(discord.ui.View):
    def __init__(self, *, viewer_id: int, code: str, inst_snapshot: dict,
                 rarity: str, gain: int, cards_db: dict):
        super().__init__(timeout=60)
        self.viewer_id     = viewer_id
        self.code          = (code or "").strip().lower()
        self.inst_snapshot = inst_snapshot or {}
        self.rarity        = rarity
        self.gain          = int(gain)
        self.cards_db      = cards_db
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def build_preview_file(self) -> discord.File:
        return pil_to_discord_file(render_single_card_image(self.cards_db, self.inst_snapshot), "pv_sell.png")

    @discord.ui.button(label="✅ Confirmar venta", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid = str(self.viewer_id)
        ensure_user(users, uid)
        cards = users[uid].get("cards", [])
        inst  = next((c for i, c in enumerate(cards) if isinstance(c, dict) and (c.get("code") or "").strip().lower() == self.code), None)

        if inst is None:
            e = discord.Embed(title="⚠️ No se pudo vender", description="Esa carta ya no está en tu inventario.", color=0xE67E22)
            await edit_interaction_message(interaction, embed=e, attachments=[], view=None)
            self.stop()
            return

        rarity = (inst.get("rarity") or rarity_from_cards_db(cards_db, inst.get("collection"), inst.get("name")) or "common").lower()
        gain   = int(SELL_VALUES.get(rarity, 1))
        cards.remove(inst)
        users[uid]["cards"] = cards
        users[uid]["gold"]  = int(users[uid].get("gold", 0)) + gain
        from core.missions import progress as mission_progress
        sell_completed = mission_progress(users, uid, "sells", 1)
        save_users(users)
        for label, reward in sell_completed:
            users[uid]["gold"] = int(users[uid].get("gold", 0)) + reward
            save_users(users)
            try:
                from core.bot_channel import get_bot_channel
                ch = (get_bot_channel(interaction.guild) if interaction.guild else None) or interaction.channel
                await ch.send(
                    f"✅ {interaction.user.mention} completó la misión **{label}** — **+{reward}** oro 💰"
                )
            except Exception:
                pass

        e = discord.Embed(
            title="Venta confirmada",
            description=(
                f"✅ Vendiste `{self.code}` — **{inst.get('name')}** (*{inst.get('collection')}*)\n"
                f"Rareza: **{rarity_es(rarity)}**\nGanancia: **{gain}** oro\n💰 Oro ahora: **{users[uid]['gold']}**"
            ),
            color=0x2ecc71,
        )
        await edit_interaction_message(interaction, embed=e, attachments=[], view=None)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        await edit_interaction_message(interaction,
                                       embed=discord.Embed(title="Venta cancelada", description="Ok, no vendí nada 😌", color=0x95A5A6),
                                       attachments=[], view=None)
        self.stop()

    async def on_timeout(self) -> None:
        try:
            if self.message:
                for child in self.children:
                    child.disabled = True
                await self.message.edit(view=None)
        except Exception:
            pass


class SellDuplicatesSelect(discord.ui.Select):
    def __init__(self, *, viewer_id: int, options):
        super().__init__(placeholder="Elegí una repetida…", min_values=1, max_values=1, options=options)
        self.viewer_id = viewer_id

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_value = self.values[0]
        await self.view.show_selected(interaction)


class SellDuplicatesView(discord.ui.View):
    def __init__(self, *, viewer_id: int, target_user_id: str, cards_db, card_instances: List[dict], gold: int):
        super().__init__(timeout=180)
        self.viewer_id      = viewer_id
        self.target_user_id = target_user_id
        self.cards_db       = cards_db
        self.card_instances = card_instances
        self.gold           = gold
        self.selected_value = None

        counts   = counts_by_char(card_instances)
        dup_keys = [(c, n) for (c, n), qty in counts.items() if qty > 1]
        options  = []
        for (c, n) in sorted(dup_keys, key=lambda x: (str(x[0]).lower(), str(x[1]).lower())):
            rarity = rarity_from_cards_db(cards_db, c, n)
            qty    = counts[(c, n)]
            options.append(discord.SelectOption(
                label=f"{n} ({c})"[:100],
                description=f"Extras: {qty-1} | {rarity_es(rarity)} | {SELL_VALUES.get(rarity,1)} oro c/u"[:100],
                value=f"{c}||{n}",
            ))
        if options:
            self.add_item(SellDuplicatesSelect(viewer_id=viewer_id, options=options))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self, extra: str = "") -> discord.Embed:
        desc = f"Oro actual: **{self.gold}**" + (f"\n{extra}" if extra else "")
        return discord.Embed(title="💰 Vender repetidas", description=desc, color=0xf1c40f)

    async def show_selected(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        if not self.selected_value:
            await edit_interaction_message(interaction, embed=self.make_embed(), view=self)
            return
        c, n = self.selected_value.split("||", 1)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, self.target_user_id)
        inst     = users[self.target_user_id].get("cards", [])
        cnt      = counts_by_char(inst)
        qty      = cnt.get((c, n), 0)
        rarity   = rarity_from_cards_db(cards_db, c, n)
        each     = SELL_VALUES.get(rarity, 1)
        self.cards_db       = cards_db
        self.card_instances = inst
        self.gold = int(users[self.target_user_id].get("gold", 0))
        txt = f"Seleccionada: **{n}** ({c})\nTenés: **x{qty}** | Extras: **{max(qty-1,0)}**\nValor: **{each}** oro c/u\n\n*(vende la peor por valor primero)*"
        await edit_interaction_message(interaction, embed=self.make_embed(txt), view=self)

    @discord.ui.button(label="Vender 1 extra", style=discord.ButtonStyle.primary)
    async def sell_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.target_user_id != str(self.viewer_id):
            await interaction.response.send_message("No podés vender cartas de otro 🙃", ephemeral=True)
            return
        if not self.selected_value:
            await interaction.response.send_message("Elegí una carta primero 🙃", ephemeral=True)
            return
        c, n = self.selected_value.split("||", 1)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, self.target_user_id)
        inst   = users[self.target_user_id]["cards"]
        rarity = rarity_from_cards_db(cards_db, c, n)
        each   = SELL_VALUES.get(rarity, 1)
        removed = remove_one_extra_instance(inst, c, n)
        if not removed:
            await interaction.response.send_message("No tenés extras para vender.", ephemeral=True)
            return
        users[self.target_user_id]["gold"] = int(users[self.target_user_id].get("gold", 0)) + each
        save_users(users)
        await interaction.response.send_message(f"✅ Vendiste **1x {n}** por **{each}** oro.", ephemeral=True)
        await self.show_selected(interaction)

    @discord.ui.button(label="Vender TODAS", style=discord.ButtonStyle.success)
    async def sell_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.target_user_id != str(self.viewer_id):
            await interaction.response.send_message("No podés vender cartas de otro 🙃", ephemeral=True)
            return
        if not self.selected_value:
            await interaction.response.send_message("Elegí una carta primero 🙃", ephemeral=True)
            return
        c, n = self.selected_value.split("||", 1)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        ensure_user(users, self.target_user_id)
        inst     = users[self.target_user_id]["cards"]
        rarity   = rarity_from_cards_db(cards_db, c, n)
        each     = SELL_VALUES.get(rarity, 1)
        removed_list = remove_all_extras_instances(inst, c, n)
        if not removed_list:
            await interaction.response.send_message("No tenés extras para vender.", ephemeral=True)
            return
        gain = len(removed_list) * each
        users[self.target_user_id]["gold"] = int(users[self.target_user_id].get("gold", 0)) + gain
        save_users(users)
        await interaction.response.send_message(f"✅ Vendiste **{len(removed_list)}** extras por **{gain}** oro.", ephemeral=True)
        await self.show_selected(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

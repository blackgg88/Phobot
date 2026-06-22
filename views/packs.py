from __future__ import annotations

import random

import discord

from core.cards import create_card_instance_from_meta, migrate_users_cards, normalize_cards, rarity_es
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from rendering.cards import pil_to_discord_file
from rendering.pack import create_pack_image
from views.common import ack, edit_interaction_message


class PacksOpenView(discord.ui.View):
    def __init__(self, *, viewer_id: int):
        super().__init__(timeout=180)
        self.viewer_id = viewer_id

        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid   = str(viewer_id)
        ensure_user(users, uid)
        packs = users[uid].get("packs", {})

        for rarity_key in ["common", "rare", "epic", "legendary", "mythic"]:
            self._add_pack_button(rarity_key, packs.get(rarity_key, 0))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    def _add_pack_button(self, rarity_key: str, count: int) -> None:
        if count <= 0:
            return
        labels = {
            "common":    "Abrir sobre común",
            "rare":      "Abrir sobre raro",
            "epic":      "Abrir sobre épico",
            "legendary": "Abrir sobre legendario",
            "mythic":    "Abrir sobre de evento",
        }
        styles = {
            "common":    discord.ButtonStyle.secondary,
            "rare":      discord.ButtonStyle.primary,
            "epic":      discord.ButtonStyle.success,
            "legendary": discord.ButtonStyle.danger,
            "mythic":    discord.ButtonStyle.danger,
        }
        btn = discord.ui.Button(
            label=f"{labels.get(rarity_key, rarity_key)} (x{count})",
            style=styles.get(rarity_key, discord.ButtonStyle.secondary),
        )
        async def _cb(interaction: discord.Interaction, rk=rarity_key):
            await self.open_pack(interaction, rk)
        btn.callback = _cb
        self.add_item(btn)

    def make_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🎁 Sobres",
            description="Elegí qué sobre abrir. Cada sobre da **1 carta** de esa rareza.",
            color=0x9b59b6,
        )

    async def open_pack(self, interaction: discord.Interaction, rarity_key: str) -> None:
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid   = str(self.viewer_id)
        ensure_user(users, uid)
        packs = users[uid].get("packs", {})
        if packs.get(rarity_key, 0) <= 0:
            await interaction.response.send_message("No tenés ese sobre 😅", ephemeral=True)
            return

        pool = [
            {"collection": col, "name": name, "img": data["img"], "rarity": r}
            for col, chars in cards_db.items()
            for name, data in chars.items()
            if (r := (data.get("rarity", "common") or "common").lower()) == rarity_key and data.get("img")
        ]
        if not pool:
            await interaction.response.send_message("No hay cartas de esa rareza cargadas.", ephemeral=True)
            return

        pick = random.choice(pool)
        inst = create_card_instance_from_meta(pick["collection"], pick["name"], cards_db, users)
        packs[rarity_key] = int(packs.get(rarity_key, 0)) - 1
        users[uid]["packs"] = packs
        users[uid]["cards"].append(inst)
        save_users(users)

        pick["value"] = inst["value"]
        img = create_pack_image([pick])
        f   = pil_to_discord_file(img, "pack_open.png")

        e = discord.Embed(
            title="🎁 Sobre abierto",
            description=(
                f"Te salió: **{pick['name']}** (*{pick['collection']}*)\n"
                f"Rareza: **{rarity_es(inst['rarity'])}**\n"
                f"Código: `{inst['code']}`\nValor: **P{inst['value']}**"
            ),
            color=0x2ecc71,
        )
        e.set_image(url="attachment://pack_open.png")
        await interaction.response.send_message(embed=e, file=f)

        new_view = PacksOpenView(viewer_id=self.viewer_id)
        await interaction.message.edit(embed=new_view.make_embed(), view=new_view)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

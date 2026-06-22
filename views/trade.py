from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import discord

from core.cards import (
    find_instance_by_code, migrate_users_cards, normalize_cards,
)
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from rendering.cards import pil_to_discord_file
from rendering.trade import build_trade_image
from views.common import ack, edit_interaction_message

ACTIVE_TRADE_USERS: Dict[int, int] = {}
ACTIVE_TRADES:      Dict[int, "TradeSession"] = {}
_trade_id_counter = 0


def _next_trade_id() -> int:
    global _trade_id_counter
    _trade_id_counter += 1
    return _trade_id_counter


@dataclass
class TradeSession:
    trade_id:   int
    a_user_id:  int
    b_user_id:  int
    a_codes:    List[str] = field(default_factory=list)
    b_codes:    List[str] = field(default_factory=list)
    a_confirm:  bool = False
    b_confirm:  bool = False
    channel_id: Optional[int] = None
    message_id: Optional[int] = None

    def is_participant(self, uid: int) -> bool:
        return uid in (self.a_user_id, self.b_user_id)

    def codes_for(self, uid: int) -> List[str]:
        return self.a_codes if uid == self.a_user_id else self.b_codes

    def set_codes(self, uid: int, codes: List[str]) -> None:
        if uid == self.a_user_id:
            self.a_codes = codes
        else:
            self.b_codes = codes
        self.a_confirm = False
        self.b_confirm = False

    def confirmed(self, uid: int) -> None:
        if uid == self.a_user_id:
            self.a_confirm = True
        else:
            self.b_confirm = True

    def is_ready(self) -> bool:
        return self.a_confirm and self.b_confirm

    def cancel(self) -> None:
        ACTIVE_TRADE_USERS.pop(self.a_user_id, None)
        ACTIVE_TRADE_USERS.pop(self.b_user_id, None)
        ACTIVE_TRADES.pop(self.trade_id, None)


async def _edit_trade_shared_message(client: discord.Client, session: TradeSession,
                                     embed: discord.Embed, view: "TradeView") -> None:
    if session.channel_id and session.message_id:
        try:
            channel = client.get_channel(session.channel_id)
            if channel:
                msg = await channel.fetch_message(session.message_id)
                await msg.edit(embed=embed, view=view, attachments=[])
        except Exception:
            pass


async def _trade_payload(client: discord.Client, session: TradeSession, cards_db: dict, users: dict) -> Tuple[discord.Embed, discord.File, "TradeView"]:
    def _insts(uid: int, codes: List[str]) -> List[dict]:
        return [
            c for c in users.get(str(uid), {}).get("cards", [])
            if isinstance(c, dict) and c.get("code", "") in codes
        ]

    a_insts = _insts(session.a_user_id, session.a_codes)
    b_insts = _insts(session.b_user_id, session.b_codes)

    try:
        a_user = await client.fetch_user(session.a_user_id)
        a_name = a_user.display_name
    except Exception:
        a_name = str(session.a_user_id)
    try:
        b_user = await client.fetch_user(session.b_user_id)
        b_name = b_user.display_name
    except Exception:
        b_name = str(session.b_user_id)

    img = build_trade_image(cards_db, a_insts=a_insts, b_insts=b_insts, a_name=a_name, b_name=b_name)
    f   = pil_to_discord_file(img, "trade.png")

    a_stat = "✅" if session.a_confirm else "⏳"
    b_stat = "✅" if session.b_confirm else "⏳"
    e = discord.Embed(
        title="🔄 Intercambio",
        description=(
            f"**{a_name}** ({a_stat}) ofrece: {', '.join(f'`{c}`' for c in session.a_codes) or '*(nada)*'}\n"
            f"**{b_name}** ({b_stat}) ofrece: {', '.join(f'`{c}`' for c in session.b_codes) or '*(nada)*'}\n\n"
            "Usá **Agregar cartas** para editar tu oferta, y **Confirmar** cuando estés listo."
        ),
        color=0x3498db,
    ).set_image(url="attachment://trade.png")

    view = TradeView(session=session)
    return e, f, view


class TradeCodesModal(discord.ui.Modal, title="Agregar cartas al intercambio"):
    codes_input = discord.ui.TextInput(
        label="Códigos de carta (separados por espacio o coma)",
        placeholder="Ej: abc123 def456",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, *, session: TradeSession):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        uid = interaction.user.id
        if not self.session.is_participant(uid):
            await interaction.followup.send("No sos parte de este intercambio.", ephemeral=True)
            return

        raw   = str(self.codes_input.value).strip()
        codes = [c.strip().lower() for c in raw.replace(",", " ").split() if c.strip()]

        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))

        ensure_user(users, str(uid))
        owned_codes = {
            (c.get("code") or "").strip().lower()
            for c in users.get(str(uid), {}).get("cards", [])
            if isinstance(c, dict)
        }
        invalid = [c for c in codes if c not in owned_codes]
        if invalid:
            await interaction.followup.send(f"No encontré en tu inventario: {', '.join(f'`{i}`' for i in invalid)}", ephemeral=True)
            return

        self.session.set_codes(uid, codes)
        e, f, view = await _trade_payload(interaction.client, self.session, cards_db, users)
        await interaction.followup.send(embed=e, file=f, view=view)
        await _edit_trade_shared_message(interaction.client, self.session, e, view)
        self.session.message_id = None


class TradeInviteView(discord.ui.View):
    def __init__(self, *, session: TradeSession):
        super().__init__(timeout=120)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.b_user_id:
            await interaction.response.send_message("Esta invitación no es para vos.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Aceptar", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))

        ACTIVE_TRADE_USERS[self.session.a_user_id] = self.session.trade_id
        ACTIVE_TRADE_USERS[self.session.b_user_id] = self.session.trade_id
        ACTIVE_TRADES[self.session.trade_id]        = self.session

        e, f, view = await _trade_payload(interaction.client, self.session, cards_db, users)
        self.session.channel_id = interaction.channel_id

        msg = await interaction.followup.send(embed=e, file=f, view=view)
        if hasattr(msg, "id"):
            self.session.message_id = msg.id

        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

    @discord.ui.button(label="❌ Rechazar", style=discord.ButtonStyle.danger)
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        self.session.cancel()
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=discord.Embed(title="Intercambio rechazado", color=0xe74c3c), view=self)
        self.stop()


class TradeView(discord.ui.View):
    def __init__(self, *, session: TradeSession):
        super().__init__(timeout=300)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.session.is_participant(interaction.user.id):
            await interaction.response.send_message("No sos parte de este intercambio.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🃏 Agregar cartas", style=discord.ButtonStyle.primary)
    async def add_cards_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TradeCodesModal(session=self.session))

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        uid = interaction.user.id
        self.session.confirmed(uid)

        if not self.session.is_ready():
            await interaction.followup.send("⏳ Esperando confirmación del otro jugador…", ephemeral=True)
            return

        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))

        ensure_user(users, str(self.session.a_user_id))
        ensure_user(users, str(self.session.b_user_id))

        a_cards = users[str(self.session.a_user_id)]["cards"]
        b_cards = users[str(self.session.b_user_id)]["cards"]

        a_giving = [c for c in a_cards if isinstance(c, dict) and c.get("code", "") in self.session.a_codes]
        b_giving = [c for c in b_cards if isinstance(c, dict) and c.get("code", "") in self.session.b_codes]

        for c in a_giving:
            a_cards.remove(c)
            b_cards.append(c)
        for c in b_giving:
            b_cards.remove(c)
            a_cards.append(c)

        save_users(users)
        self.session.cancel()

        e = discord.Embed(
            title="✅ Intercambio completado",
            description=(
                f"Se intercambiaron:\n"
                f"**{len(a_giving)}** cartas de <@{self.session.a_user_id}> → <@{self.session.b_user_id}>\n"
                f"**{len(b_giving)}** cartas de <@{self.session.b_user_id}> → <@{self.session.a_user_id}>"
            ),
            color=0x2ecc71,
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, attachments=[], view=self)
        await _edit_trade_shared_message(interaction.client, self.session, e, self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        who = interaction.user.mention
        self.session.cancel()
        for child in self.children:
            child.disabled = True
        e = discord.Embed(title="❌ Intercambio cancelado", description=f"Cancelado por {who}.", color=0xe74c3c)
        await edit_interaction_message(interaction, embed=e, attachments=[], view=self)
        await _edit_trade_shared_message(interaction.client, self.session, e, self)
        self.stop()

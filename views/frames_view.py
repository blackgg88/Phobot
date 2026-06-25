from __future__ import annotations

from collections import Counter
from typing import Optional

import discord

from core.cards import (
    find_instance_by_code, migrate_users_cards, normalize_cards,
)
from core.frames import get_frame_meta, load_frames_catalog
from core.storage import get_paths, load_json
from core.tokens import is_token_code, normalize_token_code
from core.users import ensure_user, save_users
from rendering.cards import build_before_after_image, pil_to_discord_file, render_single_card_image
from rendering.fx import apply_frame_overlay
from rendering.pack import render_pver_card
from views.common import ack, edit_interaction_message


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _available_frames(users: dict, uid: str) -> Counter:
    """Marcos disponibles (no equipados) del usuario, con cantidad."""
    return Counter(users[uid].get("frames", []))


# ─── Select de marcos ─────────────────────────────────────────────────────────

class FrameSelectView(discord.ui.View):
    """
    Select con los marcos disponibles del usuario.
    Al elegir uno muestra preview antes/después + botones confirmar/cancelar.
    """

    def __init__(self, *, user_id: int, inst: dict, cards_db: dict):
        super().__init__(timeout=120)
        self.user_id  = user_id
        self.inst     = inst
        self.cards_db = cards_db

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    async def _build_select(self, interaction: discord.Interaction) -> None:
        """Carga los marcos disponibles y muestra el select."""
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        ensure_user(users, str(self.user_id))

        counts  = _available_frames(users, str(self.user_id))
        catalog = load_frames_catalog()

        if not counts:
            await interaction.response.send_message(
                "No tenés marcos disponibles. Comprá uno en `!ptienda`.",
                ephemeral=True,
            )
            return

        options = []
        for fid, qty in counts.items():
            meta = catalog.get(int(fid))
            if not meta:
                continue
            label = meta["name"][:90]
            desc  = f"{qty} disponible{'s' if qty != 1 else ''}"
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(fid),
            ))

        if not options:
            await interaction.response.send_message(
                "No encontré marcos válidos en tu inventario.",
                ephemeral=True,
            )
            return

        select = discord.ui.Select(
            placeholder="Elegí un marco...",
            options=options[:25],
        )

        async def on_select(inter: discord.Interaction):
            fid  = int(select.values[0])
            meta = get_frame_meta(fid)
            if not meta:
                await inter.response.send_message("Marco no encontrado.", ephemeral=True)
                return

            # preview antes/después
            from rendering.pack import render_pver_card
            from PIL import Image as _PILImage
            before_full = render_pver_card(self.cards_db, self.inst)
            # escalar manteniendo proporciones para que tenga el mismo alto que el después (470)
            target_h = 470
            scale    = target_h / before_full.height
            target_w = int(before_full.width * scale)
            before   = before_full.resize((target_w, target_h), _PILImage.LANCZOS)
            inst_with_frame = {**self.inst, "frame_id": fid}
            after  = render_single_card_image(self.cards_db, inst_with_frame)
            combo  = build_before_after_image(before, after)
            f      = pil_to_discord_file(combo, "frame_preview.png")

            confirm_view = ConfirmApplyFrameView(
                user_id=self.user_id, inst=self.inst, frame_meta=meta, fid=fid,
            )
            e = discord.Embed(
                title=f"🖼️ Marco: {meta['name']}",
                description=(
                    f"Carta: **{self.inst.get('name')}** — `{self.inst.get('code')}`\n"
                    f"¿Aplicar este marco?"
                ),
                color=0x9b59b6,
            ).set_image(url="attachment://frame_preview.png")

            await inter.response.edit_message(embed=e, attachments=[f], view=confirm_view)

        select.callback = on_select

        view = discord.ui.View(timeout=120)
        view.add_item(select)

        e = discord.Embed(
            title="🖼️ Elegí un marco",
            description=f"Seleccioná el marco para **{self.inst.get('name')}**:",
            color=0x9b59b6,
        )
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)


# ─── Vista principal de !pver sin marco ───────────────────────────────────────

class ApplyFrameView(discord.ui.View):
    """
    Botón que aparece en !pver cuando la carta NO tiene marco.
    Solo visible para el dueño.
    """

    def __init__(self, *, user_id: int, inst: dict, cards_db: dict):
        super().__init__(timeout=120)
        self.user_id  = user_id
        self.inst     = inst
        self.cards_db = cards_db

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🖼️ Aplicar marco", style=discord.ButtonStyle.primary)
    async def apply_frame_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        picker = FrameSelectView(
            user_id=self.user_id, inst=self.inst, cards_db=self.cards_db,
        )
        await picker._build_select(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()


# ─── Vista principal de !pver con marco ───────────────────────────────────────

class RemoveFrameView(discord.ui.View):
    """
    Botón que aparece en !pver cuando la carta YA tiene marco.
    Solo visible para el dueño.
    """

    def __init__(self, *, user_id: int, inst: dict, cards_db: dict):
        super().__init__(timeout=120)
        self.user_id  = user_id
        self.inst     = inst
        self.cards_db = cards_db

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="❌ Quitar marco", style=discord.ButtonStyle.danger)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid  = str(self.user_id)
        code = self.inst.get("code", "")
        ensure_user(users, uid)
        inst = find_instance_by_code(users[uid].get("cards", []), code)

        if not inst or inst.get("frame_id") is None:
            await interaction.followup.send("Esa carta no tiene marco.", ephemeral=True)
            return

        fid = inst["frame_id"]
        del inst["frame_id"]
        users[uid].setdefault("frames", []).append(fid)
        save_users(users)

        meta = get_frame_meta(fid)
        name_str = meta["name"] if meta else f"#{fid}"
        e = discord.Embed(
            title="✅ Marco removido",
            description=f"El marco **{name_str}** fue retirado de **{inst.get('name')}** (`{code}`). Volvió a tu inventario.",
            color=0x2ecc71,
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, view=self)
        self.stop()

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.secondary)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()


# ─── Confirm apply ────────────────────────────────────────────────────────────

class ConfirmApplyFrameView(discord.ui.View):
    def __init__(self, *, user_id: int, inst: dict, frame_meta: dict, fid: int):
        super().__init__(timeout=60)
        self.user_id    = user_id
        self.inst       = inst
        self.frame_meta = frame_meta
        self.fid        = fid

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Aplicar", style=discord.ButtonStyle.success)
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)

        uid  = str(self.user_id)
        code = self.inst.get("code", "")
        ensure_user(users, uid)
        inst = find_instance_by_code(users[uid].get("cards", []), code)

        if not inst:
            await interaction.followup.send("La carta ya no está en tu inventario.", ephemeral=True)
            return

        frames = users[uid].get("frames", [])
        if self.fid not in frames:
            await interaction.followup.send("Ya no tenés ese marco disponible.", ephemeral=True)
            return

        inst["frame_id"] = self.fid
        frames.remove(self.fid)
        save_users(users)

        e = discord.Embed(
            title="✅ Marco aplicado",
            description=(
                f"Marco **{self.frame_meta['name']}** aplicado a "
                f"**{inst.get('name')}** (`{code}`).\n"
                f"Usá `!pver {code}` para verla con el marco."
            ),
            color=0x2ecc71,
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, attachments=[], view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(
            interaction,
            embed=discord.Embed(title="Cancelado", color=0x95a5a6),
            attachments=[],
            view=self,
        )
        self.stop()


# ─── Modals legacy (token) ────────────────────────────────────────────────────

class FrameIdModal(discord.ui.Modal, title="Aplicar marco"):
    """Mantenido por compatibilidad — ya no se usa en !pver."""
    frame_id_input = discord.ui.TextInput(
        label="ID del marco", placeholder="Ej: 1", min_length=1, max_length=4,
    )
    card_code_input = discord.ui.TextInput(
        label="Código de carta", placeholder="Ej: abc123", min_length=6, max_length=7,
    )

    def __init__(self, *, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        try:
            fid = int(str(self.frame_id_input.value).strip())
        except ValueError:
            await interaction.followup.send("ID de marco inválido.", ephemeral=True)
            return
        code = str(self.card_code_input.value).strip().lower()
        meta = get_frame_meta(fid)
        if not meta:
            await interaction.followup.send(f"No existe el marco con ID **{fid}**.", ephemeral=True)
            return
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        uid = str(self.user_id)
        ensure_user(users, uid)
        if fid not in users[uid].get("frames", []):
            await interaction.followup.send(f"No tenés el marco **{meta['name']}**.", ephemeral=True)
            return
        inst = find_instance_by_code(users[uid].get("cards", []), code)
        if inst is None:
            await interaction.followup.send("No encontré esa carta en tu inventario.", ephemeral=True)
            return
        view   = ConfirmApplyFrameView(user_id=self.user_id, inst=inst, frame_meta=meta, fid=fid)
        before = render_single_card_image(cards_db, inst)
        after  = apply_frame_overlay(before.copy(), meta)
        combo  = build_before_after_image(before, after)
        f      = pil_to_discord_file(combo, "frame_preview.png")
        e = discord.Embed(
            title=f"🖼️ Aplicar marco: {meta['name']}",
            description=f"Carta: **{inst.get('name')}** — Código: `{code}`\n¿Aplicar?",
            color=0x9b59b6,
        ).set_image(url="attachment://frame_preview.png")
        await interaction.followup.send(embed=e, file=f, view=view)


class TokenCodeModal(discord.ui.Modal, title="Aplicar token"):
    token_input = discord.ui.TextInput(
        label="Código del token (sin !)", placeholder="Ej: abcde", min_length=5, max_length=6,
    )
    card_code_input = discord.ui.TextInput(
        label="Código de carta", placeholder="Ej: abc123", min_length=6, max_length=7,
    )

    def __init__(self, *, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await ack(interaction)
        raw_token = str(self.token_input.value).strip()
        card_code = str(self.card_code_input.value).strip().lower()
        token_code = normalize_token_code(raw_token)
        if not is_token_code(token_code):
            await interaction.followup.send("Código de token inválido.", ephemeral=True)
            return
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        uid = str(self.user_id)
        ensure_user(users, uid)
        owned_tokens = users[uid].get("tokens", [])
        token_inst   = next((t for t in owned_tokens if isinstance(t, dict) and t.get("code") == token_code), None)
        if not token_inst:
            await interaction.followup.send(f"No tenés el token `{token_code}`.", ephemeral=True)
            return
        inst = find_instance_by_code(users[uid].get("cards", []), card_code)
        if not inst:
            await interaction.followup.send("No encontré esa carta en tu inventario.", ephemeral=True)
            return
        view = TokenApplyConfirmView(user_id=self.user_id, token_inst=token_inst, card_inst=inst, cards_db=cards_db)
        e = discord.Embed(
            title="🎭 Aplicar token",
            description=f"Carta: **{inst.get('name')}** | Token: `{token_code}`\n¿Confirmar?",
            color=0xe74c3c,
        )
        await interaction.followup.send(embed=e, view=view)


class TokenApplyConfirmView(discord.ui.View):
    def __init__(self, *, user_id: int, token_inst: dict, card_inst: dict, cards_db: dict):
        super().__init__(timeout=60)
        self.user_id    = user_id
        self.token_inst = token_inst
        self.card_inst  = card_inst
        self.cards_db   = cards_db

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Eso no es tuyo 😅", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        users_path, cards_path, _ = get_paths()
        users    = load_json(users_path, {})
        cards_db = normalize_cards(load_json(cards_path, {}))
        if migrate_users_cards(users, cards_db):
            save_users(users)
        uid       = str(self.user_id)
        card_code = self.card_inst.get("code", "")
        tok_code  = self.token_inst.get("code", "")
        ensure_user(users, uid)
        card_inst  = find_instance_by_code(users[uid].get("cards", []), card_code)
        token_inst = next((t for t in users[uid].get("tokens", []) if isinstance(t, dict) and t.get("code") == tok_code), None)
        if not card_inst or not token_inst:
            await interaction.followup.send("No se encontró la carta o el token.", ephemeral=True)
            return
        card_inst["token_code"] = tok_code
        card_inst["token_img"]  = token_inst.get("img")
        users[uid]["tokens"].remove(token_inst)
        save_users(users)
        e = discord.Embed(
            title="✅ Token aplicado",
            description=f"Token `{tok_code}` aplicado a **{card_inst.get('name')}** (`{card_code}`).",
            color=0x2ecc71,
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=discord.Embed(title="Cancelado", color=0x95a5a6), view=self)
        self.stop()


# ─── Aliases por compatibilidad ───────────────────────────────────────────────

class PVerFrameView(RemoveFrameView):
    """Alias legacy — carta con marco."""
    pass


class ConfirmRemoveFrameView(RemoveFrameView):
    """Alias legacy."""
    pass

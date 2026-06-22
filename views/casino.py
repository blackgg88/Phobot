from __future__ import annotations

import asyncio
import random
from typing import List, Optional

import discord

from config import CASINO_MAX_BET, CASINO_MIN_BET
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users
from views.common import ack, edit_interaction_message


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_user(uid: str):
    users_path, _, _ = get_paths()
    users = load_json(users_path, {})
    ensure_user(users, uid)
    return users


def _save(users):
    save_users(users)


# ─── Blackjack ────────────────────────────────────────────────────────────────

def _new_deck() -> List[str]:
    suits  = ["♠", "♥", "♦", "♣"]
    values = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
    deck   = [f"{v}{s}" for s in suits for v in values]
    random.shuffle(deck)
    return deck


def _card_value(card: str) -> int:
    v = card[:-1]
    if v in ("J", "Q", "K"):
        return 10
    if v == "A":
        return 11
    return int(v)


def _hand_value(hand: List[str]) -> int:
    val  = sum(_card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[:-1] == "A")
    while val > 21 and aces:
        val  -= 10
        aces -= 1
    return val


def _hand_str(hand: List[str]) -> str:
    return " ".join(hand)


class BlackjackView(discord.ui.View):
    def __init__(self, *, user_id: int, bet: int):
        super().__init__(timeout=120)
        self.user_id  = user_id
        self.bet      = bet
        self.deck     = _new_deck()
        self.player   = [self.deck.pop(), self.deck.pop()]
        self.dealer   = [self.deck.pop(), self.deck.pop()]
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("No es tu partida 😅", ephemeral=True)
            return False
        return True

    def status_embed(self, *, reveal_dealer: bool = False, result_text: str = "") -> discord.Embed:
        pv = _hand_value(self.player)
        dv = _hand_value(self.dealer)
        dealer_show = _hand_str(self.dealer) if reveal_dealer else f"{self.dealer[0]} ??"
        desc = (
            f"**Tu mano:** {_hand_str(self.player)} = **{pv}**\n"
            f"**Dealer:** {dealer_show}" + (f" = **{dv}**" if reveal_dealer else "") +
            (f"\n\n{result_text}" if result_text else "")
        )
        color = 0x2ecc71 if "ganaste" in result_text.lower() else (0xe74c3c if "perdiste" in result_text.lower() else 0x3498db)
        return discord.Embed(title=f"🃏 Blackjack — Apuesta: {self.bet} oro", description=desc, color=color)

    async def _end(self, interaction: discord.Interaction, result: str, delta: int) -> None:
        self.finished = True
        for child in self.children:
            child.disabled = True

        users    = _load_user(str(self.user_id))
        uid      = str(self.user_id)
        new_gold = max(0, int(users[uid].get("gold", 0)) + delta)
        users[uid]["gold"] = new_gold
        _save(users)

        embed = self.status_embed(reveal_dealer=True, result_text=f"{result} | Oro ahora: **{new_gold}**")
        await edit_interaction_message(interaction, embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="🃏 Pedir carta", style=discord.ButtonStyle.primary)
    async def hit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        self.player.append(self.deck.pop())
        pv = _hand_value(self.player)
        if pv > 21:
            await self._end(interaction, "💥 Perdiste (pasaste de 21)", -self.bet)
        elif pv == 21:
            await self._stand(interaction)
        else:
            await edit_interaction_message(interaction, embed=self.status_embed(), view=self)

    @discord.ui.button(label="🛑 Plantarse", style=discord.ButtonStyle.secondary)
    async def stand_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        await self._stand(interaction)

    async def _stand(self, interaction: discord.Interaction) -> None:
        while _hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        pv = _hand_value(self.player)
        dv = _hand_value(self.dealer)
        if dv > 21 or pv > dv:
            await self._end(interaction, "🎉 ¡Ganaste!", +self.bet)
        elif pv == dv:
            await self._end(interaction, "🤝 Empate", 0)
        else:
            await self._end(interaction, "😔 Perdiste", -self.bet)


# ─── Dados ────────────────────────────────────────────────────────────────────

class DiceGameView(discord.ui.View):
    def __init__(self, *, user_id: int, bet: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet     = bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("No es tu partida 😅", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 Tirar dado", style=discord.ButtonStyle.primary)
    async def roll_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        roll  = random.randint(1, 6)
        won   = roll in (4, 5, 6)
        delta = self.bet if won else -self.bet

        users    = _load_user(str(self.user_id))
        uid      = str(self.user_id)
        new_gold = max(0, int(users[uid].get("gold", 0)) + delta)
        users[uid]["gold"] = new_gold
        _save(users)

        result = "🎉 ¡Ganaste!" if won else "😔 Perdiste"
        e = discord.Embed(
            title=f"🎲 Dados — Apuesta: {self.bet} oro",
            description=f"Resultado: **{roll}** {'(4-6 gana)' if won else '(1-3 pierde)'}\n{result}\nOro ahora: **{new_gold}**",
            color=0x2ecc71 if won else 0xe74c3c,
        )
        button.disabled = True
        await edit_interaction_message(interaction, embed=e, view=self)
        self.stop()


# ─── El Gato ──────────────────────────────────────────────────────────────────

CAT_PHASES = [
    ("🐱 El Gato se estira…", 3),
    ("🐱 El Gato te mira fijamente…", 3),
    ("🐱 El Gato da un paso hacia la caja…", 3),
]


class CatGameView(discord.ui.View):
    def __init__(self, *, user_id: int, bet: int):
        super().__init__(timeout=60)
        self.user_id  = user_id
        self.bet      = bet
        self.phase    = 0
        self.resolved = False
        self._update_button()

    def _update_button(self) -> None:
        self.clear_items()
        if self.phase < len(CAT_PHASES):
            label, _ = CAT_PHASES[self.phase]
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, disabled=True)
            self.add_item(btn)
        else:
            btn = discord.ui.Button(label="🎁 Abrir la caja", style=discord.ButtonStyle.primary)
            btn.callback = self._open_box
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("No es tu partida 😅", ephemeral=True)
            return False
        return True

    async def start(self, message: discord.Message) -> None:
        for i, (text, delay) in enumerate(CAT_PHASES):
            self.phase = i
            self._update_button()
            e = discord.Embed(title=f"🐱 El Gato — Apuesta: {self.bet} oro", description=text, color=0x9b59b6)
            await message.edit(embed=e, view=self)
            await asyncio.sleep(delay)

        self.phase = len(CAT_PHASES)
        self._update_button()
        e = discord.Embed(title=f"🐱 El Gato — Apuesta: {self.bet} oro",
                          description="🐱 El Gato se acerca a la caja… ¿qué habrá dentro?", color=0x9b59b6)
        await message.edit(embed=e, view=self)

    async def _open_box(self, interaction: discord.Interaction) -> None:
        if self.resolved:
            return
        self.resolved = True
        await ack(interaction)

        roll = random.random()
        if roll < 0.45:
            result, delta = "🎉 ¡El gato dejó oro! ¡Ganaste!", self.bet
        elif roll < 0.80:
            result, delta = "😔 El gato se llevó tus monedas.", -self.bet
        else:
            result, delta = "🎲 ¡El gato tiró las monedas al suelo! Empate.", 0

        users    = _load_user(str(self.user_id))
        uid      = str(self.user_id)
        new_gold = max(0, int(users[uid].get("gold", 0)) + delta)
        users[uid]["gold"] = new_gold
        _save(users)

        e = discord.Embed(
            title=f"🐱 El Gato — Apuesta: {self.bet} oro",
            description=f"{result}\nOro ahora: **{new_gold}**",
            color=0x2ecc71 if delta > 0 else (0xe74c3c if delta < 0 else 0x95a5a6),
        )
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, embed=e, view=self)
        self.stop()


# ─── Casino Lobby ─────────────────────────────────────────────────────────────

class BetModal(discord.ui.Modal, title="💰 Apostar"):
    bet_input = discord.ui.TextInput(
        label=f"Cantidad a apostar ({CASINO_MIN_BET}–{CASINO_MAX_BET})",
        placeholder="Ej: 5",
        min_length=1,
        max_length=3,
    )

    def __init__(self, *, game: str, user_id: int, gold: int):
        super().__init__()
        self.game    = game
        self.user_id = user_id
        self.gold    = gold

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            bet = int(str(self.bet_input.value).strip())
        except ValueError:
            await interaction.response.send_message("Apuesta inválida.", ephemeral=True)
            return

        if bet < CASINO_MIN_BET or bet > CASINO_MAX_BET:
            await interaction.response.send_message(
                f"Apuesta entre {CASINO_MIN_BET} y {CASINO_MAX_BET} oro.", ephemeral=True
            )
            return

        if bet > self.gold:
            await interaction.response.send_message("No tenés suficiente oro 💸", ephemeral=True)
            return

        await interaction.response.defer()

        if self.game == "blackjack":
            view  = BlackjackView(user_id=self.user_id, bet=bet)
            embed = view.status_embed()
            await interaction.followup.send(embed=embed, view=view)
        elif self.game == "dice":
            view  = DiceGameView(user_id=self.user_id, bet=bet)
            embed = discord.Embed(title=f"🎲 Dados — Apuesta: {bet}", description="Tirá el dado cuando estés listo.", color=0x3498db)
            await interaction.followup.send(embed=embed, view=view)
        elif self.game == "cat":
            view  = CatGameView(user_id=self.user_id, bet=bet)
            embed = discord.Embed(title=f"🐱 El Gato — Apuesta: {bet}", description="El Gato abre un ojo…", color=0x9b59b6)
            msg   = await interaction.followup.send(embed=embed, view=view)
            await view.start(msg)


class CasinoLobbyView(discord.ui.View):
    def __init__(self, *, user_id: int, gold: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.gold    = gold

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("El casino no es tuyo 😅", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🎰 Casino",
            description=(
                f"💰 Oro actual: **{self.gold}**\n\n"
                "**Juegos disponibles:**\n"
                "🃏 **Blackjack** — Vencé al dealer sin pasarte de 21.\n"
                "🎲 **Dados** — Sacás 4, 5 o 6: ganás. Resto: perdés.\n"
                "🐱 **El Gato** — Juego de 3 fases. ¿Qué hay en la caja?\n\n"
                f"Apuesta mín: **{CASINO_MIN_BET}** | máx: **{CASINO_MAX_BET}** oro."
            ),
            color=0xf1c40f,
        )

    async def _open_modal(self, interaction: discord.Interaction, game: str) -> None:
        users    = _load_user(str(self.user_id))
        uid      = str(self.user_id)
        gold     = int(users[uid].get("gold", 0))
        self.gold = gold
        if gold < CASINO_MIN_BET:
            await interaction.response.send_message("No tenés oro suficiente para apostar.", ephemeral=True)
            return
        await interaction.response.send_modal(BetModal(game=game, user_id=self.user_id, gold=gold))

    @discord.ui.button(label="🃏 Blackjack", style=discord.ButtonStyle.primary)
    async def blackjack_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_modal(interaction, "blackjack")

    @discord.ui.button(label="🎲 Dados", style=discord.ButtonStyle.secondary)
    async def dice_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_modal(interaction, "dice")

    @discord.ui.button(label="🐱 El Gato", style=discord.ButtonStyle.success)
    async def cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_modal(interaction, "cat")

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ack(interaction)
        for child in self.children:
            child.disabled = True
        await edit_interaction_message(interaction, view=self)
        self.stop()

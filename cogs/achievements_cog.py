from __future__ import annotations

import time
from typing import Dict, Tuple

import discord
from discord.ext import commands

from core.achievements import (
    ACHIEVEMENTS, ACH_BY_ID,
    ensure_user_stats, check_and_award,
)
from core.bot_channel import get_bot_channel
from core.clock import now_ar, today_ar, week_key_ar
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users


def _load():
    users_path, _, _ = get_paths()
    return load_json(users_path, {})


class AchievementsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._voice_joined: Dict[Tuple[int, int], float] = {}

    # ── Helpers ────────────────────────────────────────────

    async def _notify_new(self, member: discord.Member, newly: list) -> None:
        if not newly:
            return
        channel = get_bot_channel(member.guild)
        if channel is None:
            channel = member.guild.system_channel
        if channel is None:
            return
        for aid in newly:
            ach = ACH_BY_ID.get(aid)
            if not ach:
                continue
            await channel.send(
                f"🏆 {member.mention} desbloqueó el logro **\"{ach['title']}\"** — *{ach['desc']}*"
            )

    def _flush_voice(self, users: dict, uid: str, join_ts: float) -> None:
        elapsed = int(time.time() - join_ts)
        if elapsed <= 0:
            return
        stats = ensure_user_stats(users, uid)
        stats["voice_seconds"] += elapsed
        wk = week_key_ar()
        stats["voice_week"][wk] = stats["voice_week"].get(wk, 0) + elapsed

    # ── on_ready: registrar miembros ya en voz al arrancar ─

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        now = time.time()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if member.bot:
                        continue
                    key = (member.id, guild.id)
                    if key not in self._voice_joined:
                        self._voice_joined[key] = now

    # ── on_message ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        uid = str(message.author.id)
        ar  = now_ar()

        users = _load()
        ensure_user(users, uid)
        stats = ensure_user_stats(users, uid)

        stats["msg_count"] += 1

        today = today_ar()
        last  = stats.get("last_msg_date", "")
        if last == "":
            stats["streak"] = 1
        elif last == today:
            pass
        else:
            from datetime import date
            try:
                diff = (date.fromisoformat(today) - date.fromisoformat(last)).days
                stats["streak"] = stats["streak"] + 1 if diff == 1 else 1
            except Exception:
                stats["streak"] = 1
        stats["last_msg_date"] = today

        newly = []
        # especiales: solo si todavía no los tiene
        if ar.hour == 3 and ar.minute == 33 and "msg_0333" not in stats["achievements"]:
            stats["achievements"].append("msg_0333")
            newly.append("msg_0333")
        if len(message.content) > 1000 and "msg_1000chars" not in stats["achievements"]:
            stats["achievements"].append("msg_1000chars")
            newly.append("msg_1000chars")

        newly += [a for a in check_and_award(stats) if a not in newly]
        save_users(users)

        if newly:
            await self._notify_new(message.author, newly)

    # ── on_reaction_add ────────────────────────────────────

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        if user.bot:
            return
        msg = reaction.message
        if not msg.guild or msg.author.bot or user.id == msg.author.id:
            return

        uid = str(msg.author.id)
        users = _load()
        ensure_user(users, uid)
        stats = ensure_user_stats(users, uid)
        stats["reactions_received"] += 1

        newly = check_and_award(stats)
        save_users(users)

        if newly:
            member = msg.guild.get_member(msg.author.id)
            if member:
                await self._notify_new(member, newly)

    # ── on_voice_state_update ──────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        uid = str(member.id)
        key = (member.id, member.guild.id)

        joined = before.channel is None and after.channel is not None
        left   = before.channel is not None and after.channel is None
        stayed = before.channel is not None and after.channel is not None

        users = _load()
        ensure_user(users, uid)
        stats = ensure_user_stats(users, uid)

        if joined:
            self._voice_joined[key] = time.time()
            members_in = len([m for m in after.channel.members if not m.bot])
            if members_in > stats.get("max_voice_with", 0):
                stats["max_voice_with"] = members_in

        if left and key in self._voice_joined:
            self._flush_voice(users, uid, self._voice_joined.pop(key))

        if stayed:
            # pantalla compartida: solo marcar si no estaba ya
            if after.self_stream and not stats.get("screen_shared"):
                stats["screen_shared"] = True
            if after.channel:
                members_in = len([m for m in after.channel.members if not m.bot])
                if members_in > stats.get("max_voice_with", 0):
                    stats["max_voice_with"] = members_in
            if before.channel != after.channel and key in self._voice_joined:
                self._flush_voice(users, uid, self._voice_joined[key])
                self._voice_joined[key] = time.time()

        newly = check_and_award(stats)
        save_users(users)
        if newly:
            await self._notify_new(member, newly)

    # ── !plogros ───────────────────────────────────────────

    @commands.command(name="plogros")
    async def plogros_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target = member or ctx.author
        uid    = str(target.id)

        users = _load()
        ensure_user(users, uid)
        stats = ensure_user_stats(users, uid)

        # sumar tiempo en voz actual (sin guardarlo, solo para mostrar)
        key = (target.id, ctx.guild.id) if ctx.guild else None
        live_seconds = 0
        if key and key in self._voice_joined:
            live_seconds = int(time.time() - self._voice_joined[key])

        unlocked = set(stats.get("achievements", []))
        save_users(users)

        total = len(ACHIEVEMENTS)
        done  = len(unlocked)
        pct   = int(done / total * 100) if total else 0

        # ── Contadores de progreso ──────────────────────────
        mc  = stats.get("msg_count", 0)
        vs  = stats.get("voice_seconds", 0) + live_seconds
        wk  = week_key_ar()
        vw_secs = stats.get("voice_week", {}).get(wk, 0) + live_seconds
        streak  = stats.get("streak", 0)

        def fmt_time(secs: int) -> str:
            h = secs // 3600
            m = (secs % 3600) // 60
            return f"{h}h {m}m" if h else f"{m}m"

        next_msg = next((n for n in [100, 500, 10_000] if mc < n), None)
        next_voice_h = next((n for n in [1, 10, 50, 100, 500, 1_000] if vs < n * 3600), None)

        counters = [
            f"💬 Mensajes: **{mc:,}**" + (f" / {next_msg:,}" if next_msg else " ✅"),
            f"🎙️ Llamadas total: **{fmt_time(vs)}**" + (f" / {next_voice_h}h" if next_voice_h else " ✅"),
            f"📅 Esta semana: **{fmt_time(vw_secs)}** / 24h",
            f"🔥 Racha: **{streak}** días",
        ]
        if live_seconds > 0:
            counters.append(f"🔴 En llamada ahora: **{fmt_time(live_seconds)}** *(incluido arriba)*")

        lines = [
            f"**{done}/{total} logros desbloqueados ({pct}%)**\n",
            "\n".join(counters),
        ]

        current_cat = None
        for ach in ACHIEVEMENTS:
            if ach["cat"] != current_cat:
                current_cat = ach["cat"]
                lines.append(f"\n{current_cat}")
            tick = "✅" if ach["id"] in unlocked else "⬜"
            lines.append(f"{tick} **{ach['title']}** — {ach['desc']}")

        e = discord.Embed(
            title=f"🏆 Logros de {target.display_name}",
            description="\n".join(lines),
            color=0xf1c40f,
        )
        await ctx.reply(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AchievementsCog(bot))

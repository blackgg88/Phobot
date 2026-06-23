from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import discord
from discord.ext import commands

from core.achievements import (
    ACHIEVEMENTS, CATEGORIES, ACH_BY_ID,
    ensure_guild_stats, check_and_award,
)
from core.clock import now_ar, today_ar, week_key_ar
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users


def _load():
    users_path, _, _ = get_paths()
    return load_json(users_path, {})


def _save(users: dict) -> None:
    save_users(users)


class AchievementsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {(user_id, guild_id): join_timestamp}
        self._voice_joined: Dict[Tuple[int, int], float] = {}

    # ── Helpers ────────────────────────────────────────────

    async def _notify_new(self, member: discord.Member, newly: list) -> None:
        """Manda un mensaje en el canal del servidor cuando alguien desbloquea un logro."""
        if not newly:
            return
        guild = member.guild
        # intenta el canal del sistema, si no el primero de texto
        channel = guild.system_channel
        if channel is None:
            channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if channel is None:
            return
        for aid in newly:
            ach = ACH_BY_ID.get(aid)
            if not ach:
                continue
            await channel.send(
                f"🏆 **{member.display_name}** desbloqueó el logro **\"{ach['title']}\"** — *{ach['desc']}*"
            )

    def _flush_voice(self, users: dict, uid: str, gid: str, join_ts: float) -> None:
        """Suma los segundos de voz desde join_ts al stat del usuario."""
        elapsed = int(time.time() - join_ts)
        if elapsed <= 0:
            return
        stats = ensure_guild_stats(users, uid, gid)
        stats["voice_seconds"] += elapsed

        wk = week_key_ar()
        stats["voice_week"][wk] = stats["voice_week"].get(wk, 0) + elapsed

    # ── on_message ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        uid = str(message.author.id)
        gid = str(message.guild.id)
        ar  = now_ar()

        users = _load()
        ensure_user(users, uid)
        stats = ensure_guild_stats(users, uid, gid)

        # conteo de mensajes
        stats["msg_count"] += 1

        # racha de días consecutivos
        today = today_ar()
        last  = stats.get("last_msg_date", "")
        if last == "":
            stats["streak"] = 1
        elif last == today:
            pass  # mismo día, no cambia la racha
        else:
            from datetime import date
            try:
                last_d  = date.fromisoformat(last)
                today_d = date.fromisoformat(today)
                diff    = (today_d - last_d).days
                if diff == 1:
                    stats["streak"] += 1
                else:
                    stats["streak"] = 1
            except Exception:
                stats["streak"] = 1
        stats["last_msg_date"] = today

        # 03:33 exactas (hora Argentina)
        if ar.hour == 3 and ar.minute == 33 and "msg_0333" not in stats["achievements"]:
            stats["achievements"].append("msg_0333")
            await self._notify_new(message.author, ["msg_0333"])

        # mensaje > 1000 caracteres
        if len(message.content) > 1000 and "msg_1000chars" not in stats["achievements"]:
            stats["achievements"].append("msg_1000chars")
            await self._notify_new(message.author, ["msg_1000chars"])

        newly = check_and_award(stats)
        _save(users)

        if newly:
            # filtra los que ya notificamos arriba para no duplicar
            newly = [a for a in newly if a not in ("msg_0333", "msg_1000chars")]
            await self._notify_new(message.author, newly)

    # ── on_reaction_add ────────────────────────────────────

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        if user.bot:
            return
        msg = reaction.message
        if not msg.guild or msg.author.bot:
            return
        if user.id == msg.author.id:
            return  # no se cuenta reaccionarse a uno mismo

        uid = str(msg.author.id)
        gid = str(msg.guild.id)

        users = _load()
        ensure_user(users, uid)
        stats = ensure_guild_stats(users, uid, gid)
        stats["reactions_received"] += 1

        newly = check_and_award(stats)
        _save(users)

        if newly and msg.guild:
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
        gid = str(member.guild.id)
        key = (member.id, member.guild.id)

        joined  = before.channel is None and after.channel is not None
        left    = before.channel is not None and after.channel is None
        stayed  = before.channel is not None and after.channel is not None

        users = _load()
        ensure_user(users, uid)
        stats = ensure_guild_stats(users, uid, gid)

        if joined:
            self._voice_joined[key] = time.time()
            # miembros en el canal (incluye al que entró)
            members_in = len([m for m in after.channel.members if not m.bot])
            if members_in > stats.get("max_voice_with", 0):
                stats["max_voice_with"] = members_in

        if left and key in self._voice_joined:
            self._flush_voice(users, uid, gid, self._voice_joined.pop(key))

        if stayed:
            # pantalla compartida
            if after.self_stream and not stats.get("screen_shared"):
                stats["screen_shared"] = True
            # puede haber cambiado de canal: actualiza miembros
            if after.channel:
                members_in = len([m for m in after.channel.members if not m.bot])
                if members_in > stats.get("max_voice_with", 0):
                    stats["max_voice_with"] = members_in
            # flush parcial si cambió de canal para no perder tiempo
            if before.channel != after.channel and key in self._voice_joined:
                self._flush_voice(users, uid, gid, self._voice_joined[key])
                self._voice_joined[key] = time.time()

        newly = check_and_award(stats)
        _save(users)
        if newly:
            await self._notify_new(member, newly)

    # ── !plogros ───────────────────────────────────────────

    @commands.command(name="plogros")
    async def plogros_cmd(self, ctx: commands.Context, *, member: discord.Member = None) -> None:
        target = member or ctx.author
        uid    = str(target.id)
        gid    = str(ctx.guild.id)

        users = _load()
        ensure_user(users, uid)
        stats    = ensure_guild_stats(users, uid, gid)
        unlocked = set(stats.get("achievements", []))
        _save(users)

        total     = len(ACHIEVEMENTS)
        done      = len(unlocked)
        pct       = int(done / total * 100) if total else 0

        lines = [f"**{done}/{total} logros desbloqueados ({pct}%)**\n"]
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
        e.set_footer(text=f"Servidor: {ctx.guild.name}")
        await ctx.reply(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AchievementsCog(bot))

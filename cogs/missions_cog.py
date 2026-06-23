from __future__ import annotations

import time

import discord
from discord.ext import commands

from core.missions import MISSIONS, ensure_missions, format_reset_countdown, progress
from core.storage import get_paths, load_json
from core.users import ensure_user, save_users


async def _notify_completed(ctx_or_channel, label: str, reward: int) -> None:
    """Manda mensaje público cuando se completa una misión."""
    try:
        await ctx_or_channel.send(
            f"✅ **Misión completada:** {label} — **+{reward}** oro 💰"
        )
    except Exception:
        pass


class MissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # uid → timestamp de entrada al canal de voz actual (por guild)
        self._voice_join: dict[str, float] = {}

    def _load_users(self) -> dict:
        users_path, _, _ = get_paths()
        return load_json(users_path, {})

    # ── Comando !pmisiones ───────────────────────────────────────────────────

    @commands.command(name="pmisiones")
    async def pmisiones_cmd(self, ctx: commands.Context) -> None:
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        uid   = str(ctx.author.id)
        ensure_user(users, uid)

        data    = ensure_missions(users, uid)
        save_users(users)
        reset   = format_reset_countdown()

        lines = []
        for m in MISSIONS:
            done  = m["id"] in data.get("rewarded", [])
            val   = data.get(m["key"], 0)
            goal  = m["goal"]
            # mostrar en minutos si es voz
            if m["key"] == "voice_seconds":
                val_str  = f"{min(val // 60, goal // 60)}/{goal // 60} min"
            else:
                val_str  = f"{min(val, goal)}/{goal}"
            tick  = "✅" if done else "⬜"
            lines.append(f"{tick} **{m['label']}** — {val_str} | +{m['reward']} oro")

        completed = sum(1 for m in MISSIONS if m["id"] in data.get("rewarded", []))
        total     = len(MISSIONS)

        e = discord.Embed(
            title="📋 Misiones diarias",
            description="\n".join(lines),
            color=0xf39c12,
        )
        e.set_footer(text=f"Reinicio en {reset}  •  {completed}/{total} completadas")
        await ctx.reply(embed=e)

    # ── Mensajes ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        uid = str(message.author.id)
        users_path, _, _ = get_paths()
        users = load_json(users_path, {})
        ensure_user(users, uid)
        newly = progress(users, uid, "msg", 1)
        save_users(users)
        for label, reward in newly:
            users[uid]["gold"] = int(users[uid].get("gold", 0)) + reward
            save_users(users)
            await _notify_completed(message.channel, label, reward)

    # ── Voz ──────────────────────────────────────────────────────────────────

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
        key = f"{uid}:{member.guild.id}"
        now = time.time()

        joined  = before.channel is None and after.channel is not None
        left    = before.channel is not None and after.channel is None

        if joined:
            self._voice_join[key] = now
        elif left and key in self._voice_join:
            elapsed = int(now - self._voice_join.pop(key))
            if elapsed <= 0:
                return
            users_path, _, _ = get_paths()
            users = load_json(users_path, {})
            ensure_user(users, uid)
            newly = progress(users, uid, "voice_seconds", elapsed)
            save_users(users)

            if newly and before.channel:
                for label, reward in newly:
                    users[uid]["gold"] = int(users[uid].get("gold", 0)) + reward
                    save_users(users)
                    try:
                        await before.channel.guild.system_channel.send(
                            f"✅ **{member.display_name}** completó la misión: {label} — **+{reward}** oro 💰"
                        )
                    except Exception:
                        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MissionsCog(bot))

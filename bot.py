import discord
from discord.ext import commands
import os
import random
import asyncio
import asyncpg

# ---------------- INTENTS ----------------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- SETTINGS ----------------

LEVEL_CHANNEL_ID = 1510080367892238336

voice_activity = {}
voice_last_active = {}

AFK_CHANNEL_ID = 1510048410147749898

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

# ❌ AFK ИСКЛЮЧЕНИЯ
AFK_EXEMPT_USERS = {
    1113722280573403156
}

# ---------------- ORACLE ----------------

BRODYAGA_RESPONSES = [
    "🔮 Бродяга молчит… но туман уже дал ответ.",
    "✨ Да. Но ты поймёшь это слишком поздно.",
    "⚠️ Нет. И судьба уже закрыла эту дверь.",
    "🌙 Возможно… если не свернёшь с пути.",
    "🕯️ Ответ спрятан в том, что ты игнорируешь.",
    "🔥 Да, но цена тебе не понравится.",
    "🌫️ Сейчас — пустота. Вернись позже.",
    "👁️ Я вижу движение… но не вижу тебя в конце пути.",
    "💀 Нет. И ты это уже чувствуешь.",
    "🌟 Да. Без сомнений и без жалости.",
    "🌀 Всё возможно, но ты сам мешаешь исходу.",
]

# ---------------- ROLES ----------------

RANK_ROLES = {
    0: 1510087235184099338,
    1: 1510083478094352537,
    5: 1510083899458453505,
    10: 1510083942068260965,
    15: 1511756823219404821,
    20: 1510083995327795260,
    25: 1511756481710526694,
    30: 1511759108104130600,
    35: 1510084322370256896,
    40: 1510084249762660373,
    120: 1511757185053360180
}

# ---------------- DATABASE ----------------

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)

    async with db_pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            xp INT DEFAULT 0,
            level INT DEFAULT 1
        )
        """)

async def get_user(user_id):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xp, level FROM users WHERE user_id=$1",
            user_id
        )

        if not row:
            await conn.execute(
                "INSERT INTO users VALUES ($1, 0, 1)",
                user_id
            )
            return {"xp": 0, "level": 1}

        return {"xp": row["xp"], "level": row["level"]}

async def update_user(user_id, xp, level):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE SET xp=$2, level=$3
        """, user_id, xp, level)

# ---------------- XP ----------------

def xp_needed(level):
    return 75 + (level - 1) * 100

def bar(xp, need):
    size = 10
    p = xp / need
    return "█" * int(p * size) + "░" * (size - int(p * size))

def get_title(level):
    return f"Level {level}"

# ---------------- LEVEL UP ----------------

async def level_up(member, data):
    while data["xp"] >= xp_needed(data["level"]):
        data["xp"] -= xp_needed(data["level"])
        data["level"] += 1

    await update_user(member.id, data["xp"], data["level"])

# ---------------- EVENTS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    data = await get_user(message.author.id)
    data["xp"] += random.randint(8, 18)

    await level_up(message.author, data)
    await update_user(message.author.id, data["xp"], data["level"])

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = member.id
    now = asyncio.get_event_loop().time()

    # XP VOICE
    if after.channel and not before.channel:
        voice_activity[uid] = now

    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)
        if start:
            duration = now - start
            data = await get_user(uid)
            data["xp"] += int(duration // 60)
            await level_up(member, data)
            await update_user(uid, data["xp"], data["level"])

    # ---------------- AFK SYSTEM ----------------
    if AFK_CHANNEL_ID and after.channel:
        afk_channel = member.guild.get_channel(AFK_CHANNEL_ID)
        if not afk_channel:
            return

        for m in after.channel.members:
            if m.bot:
                continue

            # ✅ ИСКЛЮЧЕНИЕ
            if m.id in AFK_EXEMPT_USERS:
                voice_last_active[m.id] = now
                continue

            last = voice_last_active.get(m.id, now)

            if now - last >= 900:
                try:
                    await m.move_to(afk_channel)
                    voice_last_active[m.id] = now
                except:
                    pass

        voice_last_active[uid] = now

# ---------------- TTT ----------------

WIN = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

def check(board):
    for a,b,c in WIN:
        if board[a] == board[b] == board[c] and board[a] != " ":
            return board[a]
    return None


class TTT(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__()
        self.players = [p1, p2]
        self.board = [" "] * 9
        self.turn = 0

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    await ctx.send(f"🎮 {ctx.author.mention} vs {opponent.mention}", view=TTT(ctx.author, opponent))

# ---------------- COMMANDS ----------------

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.command(name="фортуна")
async def fortuna(ctx):
    choices = []
    await ctx.send("Вводи варианты, напиши 'готово'")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        msg = await bot.wait_for("message", check=check)
        if msg.content.lower() == "готово":
            break
        choices.append(msg.content)

    await ctx.send(random.choice(choices) if choices else "❌ пусто")

# ---------------- START ----------------

@bot.event
async def setup_hook():
    await init_db()

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

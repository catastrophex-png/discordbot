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

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

# ---------------- RANK ROLES ----------------

RANK_ROLES = {
    0: 1510087235184099338,  # Ноунейм
    1: 1510083478094352537,  # Личинус
    5: 1510083899458453505,  # Бывалый
    10: 1510083942068260965, # На опыте
    15: 1510083995327795260, # Пизделка
    20: 1510084249762660373, # Пиздец
    25: 1510084322370256896, # Ебланище
    30: 1510084369598124052, # Животное
    40: 1510085042951684206  # Легенда сервера
}

# ---------------- DATABASE ----------------

async def init_db():
    global db_pool

    if not DATABASE_URL:
        print("❌ DATABASE_URL missing")
        return

    db_pool = await asyncpg.create_pool(DATABASE_URL)

    async with db_pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            xp INT DEFAULT 0,
            level INT DEFAULT 1
        )
        """)

async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xp, level FROM users WHERE user_id=$1",
            user_id
        )

        if not row:
            await conn.execute(
                "INSERT INTO users (user_id, xp, level) VALUES ($1, 0, 1)",
                user_id
            )
            return {"xp": 0, "level": 1}

        return {"xp": row["xp"], "level": row["level"]}

async def update_user(user_id: int, xp: int, level: int):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, xp, level)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET xp = $2, level = $3
        """, user_id, xp, level)

# ---------------- XP SYSTEM ----------------

def xp_needed(level):
    return 75 + (level - 1) * 100

def make_bar(xp, needed, size=10):
    percent = xp / needed
    filled = int(percent * size)
    return "█" * filled + "░" * (size - filled)

def get_title(level):
    if level == 0: return "Ноунейм"
    if level == 1: return "Личинус"
    if level < 5: return "Личинус"
    if level < 10: return "Бывалый"
    if level < 15: return "На опыте"
    if level < 20: return "Пизделка"
    if level < 25: return "Пиздец"
    if level < 30: return "Ебланище"
    if level < 40: return "Животное"
    return "Легенда сервера"

def get_role_id(level):
    # берём ближайший подходящий порог
    valid = sorted(RANK_ROLES.keys())
    chosen = 0
    for lvl in valid:
        if level >= lvl:
            chosen = lvl
    return RANK_ROLES[chosen]

async def update_role(member, level):
    role_id = get_role_id(level)
    guild = member.guild

    new_role = guild.get_role(role_id)
    if not new_role:
        return

    all_roles = [guild.get_role(r) for r in RANK_ROLES.values()]
    all_roles = [r for r in all_roles if r]

    await member.remove_roles(*[r for r in member.roles if r in all_roles])
    await member.add_roles(new_role)

async def level_up(member, data):
    leveled = False

    while data["xp"] >= xp_needed(data["level"]):
        data["xp"] -= xp_needed(data["level"])
        data["level"] += 1
        leveled = True

    if not leveled:
        return False

    await update_user(member.id, data["xp"], data["level"])
    await update_role(member, data["level"])

    channel = bot.get_channel(LEVEL_CHANNEL_ID)

    if channel:
        bar = make_bar(data["xp"], xp_needed(data["level"]))

        await channel.send(
            f"🎉 **Новый уровень!**\n\n"
            f"👤 {member.mention}\n"
            f"⭐ Уровень: **{data['level']}**\n"
            f"🏅 Роль: **{get_title(data['level'])}**\n\n"
            f"`{bar}` {data['xp']}/{xp_needed(data['level'])}"
        )

    return True

# ---------------- EVENTS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if db_pool:
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

    if after.channel and not before.channel:
        voice_activity[uid] = asyncio.get_event_loop().time()

    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)
        if not start:
            return

        duration = asyncio.get_event_loop().time() - start

        if db_pool:
            data = await get_user(uid)

            data["xp"] += int(duration // 60)

            await level_up(member, data)

            await update_user(uid, data["xp"], data["level"])

# ---------------- COMMANDS ----------------

@bot.command()
async def ping(ctx):
    await ctx.send("pong")


@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user(member.id)

    needed = xp_needed(data["level"])
    bar = make_bar(data["xp"], needed)

    await ctx.send(
        f"📊 {member.display_name}\n\n"
        f"⭐ Уровень: {data['level']}\n"
        f"🏅 Роль: {get_title(data['level'])}\n\n"
        f"`{bar}`\n"
        f"{data['xp']}/{needed} XP"
    )


@bot.command(name="фортуна")
async def fortuna(ctx):
    choices = []

    await ctx.send("🔮 Вводи варианты. Напиши 'готово' чтобы завершить.")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        msg = await bot.wait_for("message", check=check)

        if msg.content.lower() == "готово":
            break

        choices.append(msg.content)

    if not choices:
        return await ctx.send("❌ нет вариантов")

    await ctx.send(f"🔮 {random.choice(choices)}")


@bot.command()
async def ttt(ctx, opponent: discord.Member):
    await ctx.send(f"🎮 {ctx.author.mention} vs {opponent.mention} (TTT без изменений)")

# ---------------- START ----------------

@bot.event
async def setup_hook():
    await init_db()

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

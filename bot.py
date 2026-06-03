import discord
from discord.ext import commands
import os
import random
import asyncio
import requests
import io
from PIL import Image, ImageDraw, ImageFont
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

def get_rank(level):
    if level < 5: return "🧱 Cardboard"
    if level < 10: return "🧴 Plastic"
    if level < 20: return "🟤 Bronze"
    if level < 30: return "⚙️ Iron"
    if level < 40: return "🥇 Gold"
    if level < 55: return "💎 Diamond"
    if level < 70: return "🧙 Master"
    return "🕳 Dungeon Master"

def get_title(level):
    if level < 3: return "Личинус"
    if level < 7: return "Бывалый"
    if level < 12: return "На опыте"
    if level < 18: return "Пизделка"
    if level < 25: return "Пиздец"
    if level < 35: return "Ебланище"
    if level < 50: return "Животное"
    return "Легенда сервера"

# ---------------- LEVEL CARD ----------------

async def send_level_up(user, level):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    img = Image.new("RGB", (900, 300), (18, 18, 28))
    draw = ImageDraw.Draw(img)

    for y in range(300):
        draw.line([(0, y), (900, y)], fill=(20, 20 + y//20, 40 + y//10))

    try:
        font_big = ImageFont.truetype("arial.ttf", 44)
        font_name = ImageFont.truetype("arial.ttf", 36)
        font_mid = ImageFont.truetype("arial.ttf", 26)
    except:
        font_big = font_name = font_mid = ImageFont.load_default()

    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
    r = requests.get(avatar_url)
    avatar = Image.open(io.BytesIO(r.content)).convert("RGB")
    avatar = avatar.resize((180, 180))

    mask = Image.new("L", (180, 180), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 180, 180), fill=255)

    img.paste(avatar, (50, 60), mask)

    draw.text((260, 40), "LEVEL UP", fill="white", font=font_big)
    draw.text((260, 110), user.display_name, fill="white", font=font_name)
    draw.text((260, 160), f"Level: {level}", fill="cyan", font=font_mid)
    draw.text((260, 200), get_rank(level), fill="gold", font=font_mid)
    draw.text((260, 240), get_title(level), fill="orange", font=font_mid)

    path = f"lvl_{user.id}.png"
    img.save(path)

    await channel.send(
        content=f"🎉 {user.mention} level up!",
        file=discord.File(path)
    )

    os.remove(path)

# ---------------- MESSAGE XP ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    data = await get_user(user_id)

    data["xp"] += random.randint(5, 15)

    while data["xp"] >= xp_needed(data["level"]):
        data["xp"] -= xp_needed(data["level"])
        data["level"] += 1

        await send_level_up(message.author, data["level"])

    await update_user(user_id, data["xp"], data["level"])
    await bot.process_commands(message)

# ---------------- VOICE XP (FIXED) ----------------

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = member.id

    # joined voice
    if after.channel and not before.channel:
        voice_activity[uid] = asyncio.get_event_loop().time()

    # left voice
    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)
        if not start:
            return

        duration = asyncio.get_event_loop().time() - start

        data = await get_user(uid)
        data["xp"] += int(duration // 10)

        while data["xp"] >= xp_needed(data["level"]):
            data["xp"] -= xp_needed(data["level"])
            data["level"] += 1

        # 🔥 FIX: САМОЕ ВАЖНОЕ — СОХРАНЕНИЕ В БД
        await update_user(uid, data["xp"], data["level"])

# ---------------- STARTUP FIX ----------------

@bot.event
async def setup_hook():
    await init_db()

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

# ---------------- RUN ----------------

bot.run(os.getenv("TOKEN"))

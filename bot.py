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

# ---------------- CARD ----------------

async def send_level_up(user, level):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    WIDTH, HEIGHT = 900, 300
    img = Image.new("RGB", (WIDTH, HEIGHT), (18, 18, 28))
    draw = ImageDraw.Draw(img)

    for y in range(HEIGHT):
        g = int(25 + (y / HEIGHT) * 40)
        b = int(45 + (y / HEIGHT) * 80)
        draw.line([(0, y), (WIDTH, y)], fill=(20, g, b))

    try:
        font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
        font_name = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
        font_mid = ImageFont.truetype("DejaVuSans.ttf", 26)
    except:
        font_big = font_name = font_mid = ImageFont.load_default()

    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
    r = requests.get(avatar_url)
    avatar = Image.open(io.BytesIO(r.content)).convert("RGB")
    avatar = avatar.resize((170, 170))

    mask = Image.new("L", (170, 170), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 170, 170), fill=255)

    border = Image.new("L", (180, 180), 0)
    ImageDraw.Draw(border).ellipse((0, 0, 180, 180), fill=255)

    img.paste((40, 40, 60), (45, 65), border)
    img.paste(avatar, (50, 70), mask)

    draw.text((250, 35), "LEVEL UP", fill="white", font=font_big)
    draw.text((250, 100), user.display_name, fill="white", font=font_name)

    draw.text((250, 150), f"Level {level}", fill=(120, 220, 255), font=font_mid)
    draw.text((250, 185), get_rank(level), fill=(255, 200, 80), font=font_mid)
    draw.text((250, 220), get_title(level), fill=(200, 140, 255), font=font_mid)

    path = f"lvl_{user.id}.png"
    img.save(path)

    await channel.send(
        content=f"🎉 {user.mention} LEVEL UP!",
        file=discord.File(path)
    )

    os.remove(path)

# ---------------- XP ON MESSAGE ----------------

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

    # ВАЖНО: команды работают только с этим
    await bot.process_commands(message)

# ---------------- VOICE XP ----------------

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

        data = await get_user(uid)
        data["xp"] += int(duration // 10)

        while data["xp"] >= xp_needed(data["level"]):
            data["xp"] -= xp_needed(data["level"])
            data["level"] += 1

        await update_user(uid, data["xp"], data["level"])

# ---------------- COMMANDS ----------------

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user(member.id)

    await ctx.send(
        f"📊 {member.display_name}\n"
        f"Level: {data['level']}\n"
        f"XP: {data['xp']}/{xp_needed(data['level'])}\n"
        f"Rank: {get_rank(data['level'])}\n"
        f"Title: {get_title(data['level'])}"
    )

@bot.command()
async def testcard(ctx, member: discord.Member = None, level: int = 1):
    member = member or ctx.author
    await send_level_up(member, level)

# ---------------- START ----------------

@bot.event
async def on_ready():
    await init_db()
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

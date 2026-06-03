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

# ---------------- CONFIG ----------------

LEVEL_CHANNEL_ID = 1510080367892238336
DATABASE_URL = os.getenv("DATABASE_URL")

voice_activity = {}
db_pool = None

# ---------------- DB ----------------

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

# ---------------- XP ----------------

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

# ---------------- FONT ----------------

def load_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

# ---------------- FIXED CARD ----------------

async def send_level_up(user, level, xp, max_xp):
    try:
        channel = bot.get_channel(LEVEL_CHANNEL_ID)
        if not channel:
            return

        W, H = 900, 300

        img = Image.new("RGB", (W, H), (12, 12, 20))
        draw = ImageDraw.Draw(img)

        for y in range(H):
            draw.line([(0, y), (W, y)], fill=(18, 18 + y // 25, 35 + y // 10))

        font_big = load_font(44)
        font_name = load_font(36)
        font_mid = load_font(24)
        font_small = load_font(18)

        # avatar safe
        try:
            avatar_url = user.display_avatar.url
            r = requests.get(avatar_url, timeout=5)
            avatar = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except:
            avatar = Image.new("RGBA", (180, 180), (80, 80, 80, 255))

        avatar = avatar.resize((180, 180))

        mask = Image.new("L", (180, 180), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 180, 180), fill=255)

        avatar_circle = Image.new("RGBA", (180, 180))
        avatar_circle.paste(avatar, (0, 0), mask)

        border = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
        bd = ImageDraw.Draw(border)
        bd.ellipse((0, 0, 190, 190), outline=(0, 220, 255), width=4)
        border.paste(avatar_circle, (5, 5), avatar_circle)

        img.paste(border, (40, 60), border)

        draw.text((260, 40), "LEVEL UP", font=font_big, fill=(255, 255, 255))
        draw.text((260, 100), user.display_name, font=font_name, fill=(255, 255, 255))

        draw.text((260, 155), f"Level: {level}", font=font_mid, fill=(0, 220, 255))
        draw.text((260, 190), get_rank(level), font=font_mid, fill=(255, 200, 0))
        draw.text((260, 225), get_title(level), font=font_mid, fill=(200, 200, 200))

        progress = xp / max_xp if max_xp else 0

        bar_x, bar_y = 260, 265
        bar_w, bar_h = 580, 18

        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
            radius=8,
            fill=(35, 35, 55)
        )

        fill_w = int(bar_w * max(0, min(progress, 1)))

        if fill_w > 0:
            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
                radius=8,
                fill=(0, 220, 255)
            )

        draw.text((260, 240), f"{xp}/{max_xp} XP", font=font_small, fill=(180, 180, 180))

        buffer = io.BytesIO()
        img.save(buffer, "PNG")
        buffer.seek(0)

        await channel.send(
            content=f"🎉 {user.mention} level up!",
            file=discord.File(buffer, "level.png")
        )

    except Exception as e:
        print("CARD ERROR:", e)

# ---------------- XP ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    data = await get_user(message.author.id)

    data["xp"] += random.randint(5, 15)

    while data["xp"] >= xp_needed(data["level"]):
        data["xp"] -= xp_needed(data["level"])
        data["level"] += 1

        await send_level_up(
            message.author,
            data["level"],
            data["xp"],
            xp_needed(data["level"])
        )

    await update_user(message.author.id, data["xp"], data["level"])

    await bot.process_commands(message)

# ---------------- ERRORS ----------------

@bot.event
async def on_command_error(ctx, error):
    print("COMMAND ERROR:", error)
    await ctx.send(f"❌ Error: {error}")

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
    await send_level_up(member, level, 0, xp_needed(level))

# ---------------- START ----------------

@bot.event
async def on_ready():
    await init_db()
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

import discord
from discord.ext import commands
import os
import random
import json
import asyncio
import requests
import io
from PIL import Image, ImageDraw, ImageFont

# ---------------- INTENTS ----------------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- SETTINGS ----------------

LEVEL_CHANNEL_ID = 1510080367892238336
DATA_FILE = "data.json"

voice_activity = {}

# ---------------- DATA ----------------

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

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

# ---------------- LEVEL UP CARD ----------------

async def send_level_up(user, level):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    width, height = 900, 300
    img = Image.new("RGB", (width, height), (15, 15, 25))
    draw = ImageDraw.Draw(img)

    # gradient background
    for y in range(height):
        r = int(20 + y * 0.05)
        g = int(25 + y * 0.08)
        b = int(50 + y * 0.15)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # fonts
    try:
        font_big = ImageFont.truetype("arial.ttf", 42)
        font_mid = ImageFont.truetype("arial.ttf", 30)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except:
        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # avatar
    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(io.BytesIO(response.content)).convert("RGB")
    avatar = avatar.resize((180, 180))

    mask = Image.new("L", (180, 180), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((0, 0, 180, 180), fill=255)

    # shadow
    draw.ellipse((40, 60, 230, 250), fill=(0, 0, 0, 120))

    img.paste(avatar, (50, 70), mask)

    # text
    draw.text((260, 60), "LEVEL UP!", fill=(255, 255, 255), font=font_big)
    draw.text((260, 120), user.display_name, fill=(220, 220, 220), font=font_mid)

    draw.text((260, 170), f"Level {level}", fill=(0, 200, 255), font=font_mid)
    draw.text((260, 210), get_rank(level), fill=(255, 215, 0), font=font_small)
    draw.text((260, 245), get_title(level), fill=(255, 140, 0), font=font_small)

    path = f"levelup_{user.id}.png"
    img.save(path)

    await channel.send(
        content=f"🎉 {user.mention} повысил уровень!",
        file=discord.File(path)
    )

    os.remove(path)

# ---------------- TEXT XP ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    data = load_data()
    uid = str(message.author.id)

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    data[uid]["xp"] += random.randint(5, 15)

    level = data[uid]["level"]

    if data[uid]["xp"] >= xp_needed(level):
        data[uid]["level"] += 1
        data[uid]["xp"] = 0

        await send_level_up(message.author, data[uid]["level"])

    save_data(data)
    await bot.process_commands(message)

# ---------------- VOICE XP ----------------

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = str(member.id)

    if after.channel and not before.channel:
        voice_activity[uid] = True

    elif before.channel and not after.channel:
        voice_activity.pop(uid, None)

async def voice_xp_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        data = load_data()

        for uid in list(voice_activity.keys()):
            if uid not in data:
                data[uid] = {"xp": 0, "level": 1}

            data[uid]["xp"] += 1  # per minute

            level = data[uid]["level"]

            if data[uid]["xp"] >= xp_needed(level):
                data[uid]["level"] += 1
                data[uid]["xp"] = 0

        save_data(data)
        await asyncio.sleep(60)

# ---------------- COMMANDS ----------------

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)

    data = load_data()

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    level = data[uid]["level"]
    xp = data[uid]["xp"]

    await ctx.send(
        f"📊 **{member.display_name}**\n\n"
        f"🏆 Level: **{level}**\n"
        f"✨ XP: **{xp} / {xp_needed(level)}**\n"
        f"📛 Rank: **{get_rank(level)}**\n"
        f"💬 Title: **{get_title(level)}**"
    )

@bot.command()
async def ping(ctx):
    await ctx.send("🟢 бот жив")

@bot.command()
async def fortuna(ctx):
    await ctx.send("🔮 Напиши варианты, потом 'готово'")

    variants = []

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        msg = await bot.wait_for("message", check=check)
        if msg.content.lower() == "готово":
            break
        variants.append(msg.content)

    await ctx.send(f"✨ Победитель: **{random.choice(variants)}**")

# ---------------- READY ----------------

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)
    asyncio.create_task(voice_xp_loop())

# ---------------- RUN ----------------

bot.run(os.getenv("TOKEN"))

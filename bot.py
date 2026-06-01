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

# uid -> timestamp when entered voice
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

    img = Image.new("RGB", (900, 300), (18, 18, 28))
    draw = ImageDraw.Draw(img)

    for y in range(300):
        color = (18 + y//30, 18 + y//40, 35 + y//20)
        draw.line([(0, y), (900, y)], fill=color)

    try:
        font_big = ImageFont.truetype("arial.ttf", 44)
        font_name = ImageFont.truetype("arial.ttf", 38)
        font_mid = ImageFont.truetype("arial.ttf", 28)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except:
        font_big = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_mid = ImageFont.load_default()
        font_small = ImageFont.load_default()

    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(io.BytesIO(response.content)).convert("RGB")
    avatar = avatar.resize((200, 200))

    mask = Image.new("L", (200, 200), 0)
    m = ImageDraw.Draw(mask)
    m.ellipse((0, 0, 200, 200), fill=255)

    img.paste(avatar, (40, 50), mask)

    draw.text((270, 40), "LEVEL UP!", fill=(255, 255, 255), font=font_big)
    draw.text((270, 100), user.display_name, fill=(255, 255, 255), font=font_name)
    draw.text((270, 155), f"Level: {level}", fill=(120, 200, 255), font=font_mid)
    draw.text((270, 195), f"Rank: {get_rank(level)}", fill=(255, 215, 120), font=font_small)
    draw.text((270, 230), f"Title: {get_title(level)}", fill=(255, 170, 120), font=font_small)

    path = f"levelup_{user.id}.png"
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

    data = load_data()
    uid = str(message.author.id)

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    data[uid]["xp"] += random.randint(5, 15)

    while data[uid]["xp"] >= xp_needed(data[uid]["level"]):
        data[uid]["xp"] -= xp_needed(data[uid]["level"])
        data[uid]["level"] += 1
        await send_level_up(message.author, data[uid]["level"])

    save_data(data)
    await bot.process_commands(message)

# ---------------- VOICE XP (FIXED CORE) ----------------

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = str(member.id)

    # joined voice
    if after.channel and not before.channel:
        voice_activity[uid] = asyncio.get_event_loop().time()

    # left voice → calculate final chunk
    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)

        if not start:
            return

        duration = asyncio.get_event_loop().time() - start

        data = load_data()

        if uid not in data:
            data[uid] = {"xp": 0, "level": 1}

        gained = int(duration // 10)  # 1 XP per 10 sec

        data[uid]["xp"] += gained

        while data[uid]["xp"] >= xp_needed(data[uid]["level"]):
            data[uid]["xp"] -= xp_needed(data[uid]["level"])
            data[uid]["level"] += 1

        save_data(data)

# ---------------- BACKGROUND VOICE XP (REAL-TIME FIX) ----------------

async def voice_xp_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        data = load_data()
        now = asyncio.get_event_loop().time()

        for uid, start_time in list(voice_activity.items()):

            if uid not in data:
                data[uid] = {"xp": 0, "level": 1}

            # every 60 seconds = +6 XP
            seconds = now - start_time
            gained = int(seconds // 60) * 6

            if gained > 0:
                data[uid]["xp"] += gained
                voice_activity[uid] = now

                while data[uid]["xp"] >= xp_needed(data[uid]["level"]):
                    data[uid]["xp"] -= xp_needed(data[uid]["level"])
                    data[uid]["level"] += 1

        save_data(data)
        await asyncio.sleep(60)

# ---------------- COMMANDS ----------------

@bot.command()
async def ping(ctx):
    await ctx.send("🟢 bot alive")

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_data()
    uid = str(member.id)

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    level = data[uid]["level"]
    xp = data[uid]["xp"]
    need = xp_needed(level)

    await ctx.send(
        f"📊 {member.display_name}\n"
        f"Level: {level}\n"
        f"XP: {xp}/{need}\n"
        f"Rank: {get_rank(level)}\n"
        f"Title: {get_title(level)}"
    )

# ---------------- START ----------------

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)
    bot.loop.create_task(voice_xp_loop())

bot.run(os.getenv("TOKEN"))

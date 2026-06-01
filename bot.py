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

# ---------------- LEVEL UP ----------------

async def send_level_up(user, level):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    img = Image.new("RGB", (800, 250), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    for y in range(250):
        draw.line([(0, y), (800, y)], fill=(20, 20 + y//10, 50 + y//5))

    try:
        font_big = ImageFont.truetype("arial.ttf", 40)
        font_mid = ImageFont.truetype("arial.ttf", 28)
    except:
        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()

    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(io.BytesIO(response.content)).convert("RGB")
    avatar = avatar.resize((150, 150))

    mask = Image.new("L", (150, 150), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, 150, 150), fill=255)

    img.paste(avatar, (30, 50), mask)

    draw.text((220, 60), "LEVEL UP!", fill="white", font=font_big)
    draw.text((220, 120), user.display_name, fill="white", font=font_mid)
    draw.text((220, 160), f"Level: {level}", fill="cyan", font=font_mid)
    draw.text((220, 200), get_rank(level), fill="gold", font=font_mid)

    path = f"lvl_{user.id}.png"
    img.save(path)

    await channel.send(
        content=f"🎉 {user.mention} leveled up!",
        file=discord.File(path)
    )

    os.remove(path)

# ---------------- XP ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 🔥 НЕ ЛОМАЕМ ИГРЫ
    if message.content.startswith("!ttt") or message.content.startswith("!move"):
        await bot.process_commands(message)
        return

    data = load_data()
    uid = str(message.author.id)

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    data[uid]["xp"] += random.randint(5, 15)

    if data[uid]["xp"] >= xp_needed(data[uid]["level"]):
        data[uid]["xp"] = 0
        data[uid]["level"] += 1
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

            data[uid]["xp"] += 1

            if data[uid]["xp"] >= xp_needed(data[uid]["level"]):
                data[uid]["xp"] = 0
                data[uid]["level"] += 1

        save_data(data)
        await asyncio.sleep(60)

# ---------------- TIC TAC TOE ----------------

games = {}

def empty_board():
    return [" " for _ in range(9)]

def check_winner(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),
            (0,3,6),(1,4,7),(2,5,8),
            (0,4,8),(2,4,6)]
    for a,b2,c in wins:
        if b[a] == b[b2] == b[c] != " ":
            return b[a]
    return None

def render_board(b):
    return f"""
{b[0]} | {b[1]} | {b[2]}
---------
{b[3]} | {b[4]} | {b[5]}
---------
{b[6]} | {b[7]} | {b[8]}
"""

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    games[ctx.channel.id] = {
        "board": empty_board(),
        "turn": ctx.author.id,
        "p1": ctx.author.id,
        "p2": opponent.id
    }

    await ctx.send(
        f"🎮 Игра началась!\n\n{ctx.author.mention} vs {opponent.mention}\n"
        f"Напиши `!move 1-9`"
    )

@bot.command()
async def move(ctx, pos: int):
    game = games.get(ctx.channel.id)
    if not game:
        return

    if ctx.author.id not in [game["p1"], game["p2"]]:
        return

    if ctx.author.id != game["turn"]:
        return

    pos -= 1
    if game["board"][pos] != " ":
        return

    symbol = "X" if ctx.author.id == game["p1"] else "O"
    game["board"][pos] = symbol

    winner = check_winner(game["board"])

    if winner:
        await ctx.send(render_board(game["board"]) + f"\n🏆 Победил {ctx.author.mention}")
        del games[ctx.channel.id]
        return

    game["turn"] = game["p2"] if game["turn"] == game["p1"] else game["p1"]

    await ctx.send(render_board(game["board"]))

# ---------------- COMMANDS ----------------

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_data()

    uid = str(member.id)
    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    await ctx.send(
        f"📊 {member.display_name}\n"
        f"Level: {data[uid]['level']}\n"
        f"XP: {data[uid]['xp']}"
    )

@bot.command()
async def ping(ctx):
    await ctx.send("🟢 online")

# ---------------- READY ----------------

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)
    asyncio.create_task(voice_xp_loop())

bot.run(os.getenv("TOKEN"))

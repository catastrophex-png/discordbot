import discord
from discord.ext import commands
import os
import random
import json
import asyncio
from PIL import Image, ImageDraw

# ---------------- INTENTS ----------------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# ---------------- DATA ----------------

DATA_FILE = "data.json"
voice_activity = {}

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

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

# ---------------- BOT ----------------

class MyBot(commands.Bot):
    async def setup_hook(self):
        self.tree.copy_global_to(guild=None)
        await self.tree.sync()
        self.loop.create_task(voice_xp_loop())

bot = MyBot(command_prefix="!", intents=intents)
tree = bot.tree

LEVEL_CHANNEL_ID = 1510080367892238336

# ---------------- LEVEL UP ----------------

async def send_level_up(user, level):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    img = Image.new("RGB", (600, 250), (25, 25, 25))
    draw = ImageDraw.Draw(img)

    draw.text((20, 30), "LEVEL UP!", fill="white")
    draw.text((20, 80), user.name, fill="white")
    draw.text((20, 120), f"Level: {level}", fill="white")
    draw.text((20, 160), get_rank(level), fill="gold")
    draw.text((20, 200), get_title(level), fill="orange")

    path = f"levelup_{user.id}.png"
    img.save(path)

    await channel.send(
        content=f"🎉 {user.mention} повысил уровень!",
        file=discord.File(path)
    )

# ---------------- TEXT XP ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    try:
        data = load_data()
        uid = str(message.author.id)

        if uid not in data:
            data[uid] = {"xp": 0, "level": 1}

        data[uid]["xp"] += random.randint(5, 15)

        level = data[uid]["level"]
        xp = data[uid]["xp"]

        if xp >= xp_needed(level):
            data[uid]["level"] += 1
            data[uid]["xp"] = 0
            await send_level_up(message.author, data[uid]["level"])

        save_data(data)

    except Exception as e:
        print("XP ERROR:", e)

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

            level = data[uid]["level"]
            xp = data[uid]["xp"]

            if xp >= xp_needed(level):
                data[uid]["level"] += 1
                data[uid]["xp"] = 0

        save_data(data)
        await asyncio.sleep(60)

# ---------------- SLASH COMMANDS ----------------

@tree.command(name="rank", description="Показать уровень игрока")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    uid = str(member.id)

    data = load_data()

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    level = data[uid]["level"]
    xp = data[uid]["xp"]

    await interaction.response.send_message(
        f"📊 **{member.display_name}**\n\n"
        f"🏆 Level: **{level}**\n"
        f"✨ XP: **{xp} / {xp_needed(level)}**\n"
        f"📛 Rank: **{get_rank(level)}**\n"
        f"💬 Title: **{get_title(level)}**"
    )

@tree.command(name="ping", description="Проверка бота")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("бот жив 🟢")

@tree.command(name="fortuna", description="Мини-игра фортуна")
async def fortuna(interaction: discord.Interaction):
    await interaction.response.send_message("Отправляй варианты в чат, потом напиши 'готово'")

    variants = []

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    while True:
        msg = await bot.wait_for("message", check=check)
        if msg.content.lower() == "готово":
            break
        variants.append(msg.content)

    await interaction.followup.send(f"✨ Победитель: **{random.choice(variants)}**")

# ---------------- READY ----------------

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

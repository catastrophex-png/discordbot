import discord
from discord.ext import commands
import os
import random
import json
import asyncio
from PIL import Image, ImageDraw

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

# ---------------- BOT CLASS (IMPORTANT FIX) ----------------

class MyBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(voice_xp_loop())

# ---------------- BOT INIT ----------------

bot = MyBot(command_prefix="!", intents=intents)

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

            data[uid]["xp"] += 10

            level = data[uid]["level"]
            xp = data[uid]["xp"]

            if xp >= xp_needed(level):
                data[uid]["level"] += 1
                data[uid]["xp"] = 0

        save_data(data)
        await asyncio.sleep(60)

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

def give_xp(user_id, amount):
    data = load_data()
    uid = str(user_id)

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    data[uid]["xp"] += amount
    save_data(data)

class TTT(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=None)

        self.players = [p1, p2]
        self.board = [" "] * 9
        self.turn = 0

        self.build()

    def build(self):
        self.clear_items()

        for i in range(9):
            mark = self.board[i]

            btn = discord.ui.Button(
                label=mark if mark != " " else "⬜",
                style=discord.ButtonStyle.secondary,
                row=i // 3,
                disabled=(mark != " ")
            )

            async def callback(interaction, i=i):

                if interaction.user != self.players[self.turn]:
                    return await interaction.response.send_message("Не твой ход", ephemeral=True)

                if self.board[i] != " ":
                    return await interaction.response.send_message("Занято", ephemeral=True)

                self.board[i] = "❌" if self.turn == 0 else "⭕"

                winner = check(self.board)

                if winner:
                    give_xp(interaction.user.id, 50)
                    self.build()

                    for b in self.children:
                        b.disabled = True

                    return await interaction.response.edit_message(
                        content=f"🏆 Победитель: {interaction.user.mention}",
                        view=self
                    )

                if " " not in self.board:
                    self.build()

                    for b in self.children:
                        b.disabled = True

                    return await interaction.response.edit_message(
                        content="🤝 Ничья",
                        view=self
                    )

                self.turn = 1 - self.turn
                self.build()

                return await interaction.response.edit_message(
                    content=f"Ход: {self.players[self.turn].mention}",
                    view=self
                )

            btn.callback = callback
            self.add_item(btn)

# ---------------- COMMANDS ----------------

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)

    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}\nХод: {ctx.author.mention}",
        view=view
    )

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
    await ctx.send("бот жив 🟢")

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

bot.run(os.getenv("TOKEN"))

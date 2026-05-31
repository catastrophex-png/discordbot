import discord
from discord.ext import commands
import os
import random
import json
from PIL import Image, ImageDraw

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- LEVEL UP CHANNEL ----------------

LEVEL_CHANNEL_ID = 1510080367892238336  # #помойка

# ---------------- DATA ----------------

DATA_FILE = "data.json"

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
    return 100 + level * 50

def get_rank(level):
    if level < 5:
        return "🧱 Cardboard"
    elif level < 10:
        return "🧴 Plastic"
    elif level < 20:
        return "🟤 Bronze"
    elif level < 30:
        return "⚙️ Iron"
    elif level < 40:
        return "🥇 Gold"
    elif level < 55:
        return "💎 Diamond"
    elif level < 70:
        return "🧙 Master"
    return "🕳 Dungeon Master"

def get_title(level):
    if level < 3:
        return "Личинус"
    elif level < 7:
        return "Бывалый"
    elif level < 12:
        return "На опыте"
    elif level < 18:
        return "Пизделка"
    elif level < 25:
        return "Пиздец"
    elif level < 35:
        return "Ебланище"
    elif level < 50:
        return "Животное"
    return "Легенда сервера"

# ---------------- LEVEL UP IMAGE ----------------

async def send_level_up(user, level):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    rank = get_rank(level)
    title = get_title(level)

    img = Image.new("RGB", (600, 250), (25, 25, 25))
    draw = ImageDraw.Draw(img)

    draw.text((20, 30), "LEVEL UP!", fill="white")
    draw.text((20, 80), f"{user.name}", fill="white")
    draw.text((20, 120), f"Level: {level}", fill="white")
    draw.text((20, 160), f"{rank}", fill="gold")
    draw.text((20, 200), f"{title}", fill="orange")

    path = f"levelup_{user.id}.png"
    img.save(path)

    await channel.send(
        content=f"🎉 {user.mention} повысил уровень!",
        file=discord.File(path)
    )

# ---------------- XP ON MESSAGE ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    user_id = str(message.author.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {"xp": 0, "level": 1}

    data[user_id]["xp"] += random.randint(5, 15)

    level = data[user_id]["level"]
    xp = data[user_id]["xp"]

    if xp >= xp_needed(level):
        data[user_id]["level"] += 1
        data[user_id]["xp"] = 0
        await send_level_up(message.author, data[user_id]["level"])

    save_data(data)

# ---------------- KRESTIKI-NOLIKI (FIXED NO DUPLICATES) ----------------

WIN = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

def check(board):
    for a, b, c in WIN:
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
            label = mark if mark != " " else "⬜"

            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                row=i // 3,
                disabled=(mark != " ")
            )

            async def callback(interaction, i=i):
                if interaction.user != self.players[self.turn]:
                    return await interaction.response.send_message(
                        "Не твой ход",
                        ephemeral=True
                    )

                if self.board[i] != " ":
                    return await interaction.response.send_message(
                        "Занято",
                        ephemeral=True
                    )

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

                await interaction.response.edit_message(
                    content=f"Ход: {self.players[self.turn].mention}",
                    view=self
                )

            btn.callback = callback
            self.add_item(btn)

# ---------------- COMMANDS ----------------

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    game = TTT(ctx.author, opponent)

    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}\n"
        f"Ход: {ctx.author.mention}",
        view=game
    )

@bot.command()
async def fortuna(ctx):
    await ctx.send("🔮 Отправляй варианты. Напиши 'готово'")

    variants = []

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        msg = await bot.wait_for("message", check=check)

        if msg.content.lower() == "готово":
            break

        variants.append(msg.content)

    winner = random.choice(variants)
    await ctx.send(f"✨ Победитель: **{winner}** ✨")

@bot.command()
async def ping(ctx):
    await ctx.send("бот жив 🟢")

# ---------------- READY ----------------

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

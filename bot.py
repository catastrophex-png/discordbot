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

# ---------------- VOICE XP ----------------

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = str(member.id)

    if after.channel and not before.channel:
        voice_activity[uid] = asyncio.get_event_loop().time()

    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)

        if not start:
            return

        duration = asyncio.get_event_loop().time() - start

        data = load_data()

        if uid not in data:
            data[uid] = {"xp": 0, "level": 1}

        data[uid]["xp"] += int(duration // 10)

        while data[uid]["xp"] >= xp_needed(data[uid]["level"]):
            data[uid]["xp"] -= xp_needed(data[uid]["level"])
            data[uid]["level"] += 1

        save_data(data)

# ---------------- TTT FIXED ----------------

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


class TTT(discord.ui.View):
    def __init__(self, p1, p2, board=None, turn=0):
        super().__init__(timeout=None)

        self.players = [p1, p2]
        self.board = board or [" "] * 9
        self.turn = turn

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

            async def callback(interaction, index=i):

                if interaction.user != self.players[self.turn]:
                    return await interaction.response.send_message("⛔ Не твой ход", ephemeral=True)

                if self.board[index] != " ":
                    return await interaction.response.send_message("⛔ Занято", ephemeral=True)

                self.board[index] = "❌" if self.turn == 0 else "⭕"

                winner = check(self.board)

                if winner:
                    for b in self.children:
                        b.disabled = True

                    return await interaction.response.edit_message(
                        content=f"🏆 Победитель: {interaction.user.mention}",
                        view=self
                    )

                if " " not in self.board:
                    for b in self.children:
                        b.disabled = True

                    return await interaction.response.edit_message(
                        content="🤝 Ничья",
                        view=self
                    )

                self.turn = 1 - self.turn

                new_view = TTT(self.players[0], self.players[1], self.board, self.turn)

                await interaction.response.edit_message(
                    content=f"🎮 Ход: {self.players[self.turn].mention}",
                    view=new_view
                )

            btn.callback = callback
            self.add_item(btn)

# ---------------- COMMANDS ----------------

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_data()
    uid = str(member.id)

    if uid not in data:
        data[uid] = {"xp": 0, "level": 1}

    lvl = data[uid]["level"]
    xp = data[uid]["xp"]

    await ctx.send(
        f"📊 {member.display_name}\n"
        f"Level: {lvl}\n"
        f"XP: {xp}/{xp_needed(lvl)}\n"
        f"Rank: {get_rank(lvl)}\n"
        f"Title: {get_title(lvl)}"
    )

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)
    await ctx.send(f"🎮 {ctx.author.mention} vs {opponent.mention}", view=view)

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

    await ctx.send(f"🔮 Выбор...\n✨ {random.choice(choices)}")

# ---------------- START ----------------

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

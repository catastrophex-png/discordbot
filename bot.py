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

# ---------------- UI HELPERS ----------------

def load_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

def draw_bar(draw, x, y, w, h, progress, fill, bg):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=bg)

    fill_w = int(w * max(0, min(progress, 1)))
    if fill_w > 0:
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=10, fill=fill)

# ---------------- LEVEL CARD ----------------

async def send_level_up(user, level, xp, max_xp):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return

    W, H = 900, 300

    # фон
    img = Image.new("RGB", (W, H), (15, 15, 25))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        draw.line([(0, y), (W, y)], fill=(18, 18 + y // 20, 40 + y // 10))

    # шрифты
    font_big = load_font(46)
    font_name = load_font(38)
    font_mid = load_font(24)
    font_small = load_font(18)

    # аватар
    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
    r = requests.get(avatar_url)
    avatar = Image.open(io.BytesIO(r.content)).convert("RGBA")
    avatar = avatar.resize((180, 180))

    mask = Image.new("L", (180, 180), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 180, 180), fill=255)

    avatar_bg = Image.new("RGBA", (180, 180))
    avatar_bg.paste(avatar, (0, 0), mask)

    border = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.ellipse((0, 0, 190, 190), outline=(0, 220, 255), width=4)
    border.paste(avatar_bg, (5, 5), avatar_bg)

    img.paste(border, (40, 60), border)

    # текст
    draw.text((260, 40), "LEVEL UP", font=font_big, fill=(255, 255, 255))
    draw.text((260, 100), user.display_name, font=font_name, fill=(255, 255, 255))

    draw.text((260, 155), f"Level: {level}", font=font_mid, fill=(0, 220, 255))
    draw.text((260, 190), get_rank(level), font=font_mid, fill=(255, 200, 0))
    draw.text((260, 225), get_title(level), font=font_mid, fill=(200, 200, 200))

    # XP bar
    progress = xp / max_xp if max_xp else 0

    draw_bar(
        draw,
        260,
        265,
        580,
        20,
        progress,
        fill=(0, 220, 255),
        bg=(40, 40, 60)
    )

    draw.text((260, 240), f"{xp}/{max_xp} XP", font=font_small, fill=(180, 180, 180))

    # отправка
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)

    await channel.send(
        content=f"🎉 {user.mention} level up!",
        file=discord.File(buffer, "level.png")
    )

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

        await send_level_up(
            message.author,
            data["level"],
            data["xp"],
            xp_needed(data["level"])
        )

    await update_user(user_id, data["xp"], data["level"])

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

# ---------------- TTT ----------------

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
    data = await get_user(member.id)

    lvl = data["level"]
    xp = data["xp"]

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
    await init_db()
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

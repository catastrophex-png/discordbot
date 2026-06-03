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

# ---------------- START ----------------

@bot.event
async def on_ready():
    global db_pool
    print("BOT ONLINE:", bot.user)

    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL)

        async with db_pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                xp INT DEFAULT 0,
                level INT DEFAULT 1
            )
            """)

        print("DB READY")

    except Exception as e:
        print("DB ERROR:", e)

# ---------------- DATABASE ----------------

async def get_user(user_id: int):
    try:
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

    except Exception as e:
        print("GET USER ERROR:", e)
        return {"xp": 0, "level": 1}

async def update_user(user_id: int, xp: int, level: int):
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, xp, level)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id)
                DO UPDATE SET xp = $2, level = $3
            """, user_id, xp, level)

    except Exception as e:
        print("UPDATE USER ERROR:", e)

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

# ---------------- CARD ----------------

async def send_level_up(user, level):
    try:
        channel = bot.get_channel(LEVEL_CHANNEL_ID)
        if not channel:
            return

        img = Image.new("RGB", (900, 300), (18, 18, 28))
        draw = ImageDraw.Draw(img)

        for y in range(300):
            g = int(25 + (y / 300) * 40)
            b = int(45 + (y / 300) * 80)
            draw.line([(0, y), (900, y)], fill=(20, g, b))

        try:
            font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
            font_name = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
            font_mid = ImageFont.truetype("DejaVuSans.ttf", 26)
        except:
            font_big = font_name = font_mid = ImageFont.load_default()

        avatar_url = getattr(user.avatar, "url", None) or user.default_avatar.url

        try:
            r = requests.get(avatar_url, timeout=5)
            avatar = Image.open(io.BytesIO(r.content)).convert("RGB")
        except:
            avatar = Image.new("RGB", (170, 170), (120, 120, 120))

        avatar = avatar.resize((170, 170))

        mask = Image.new("L", (170, 170), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 170, 170), fill=255)

        img.paste(avatar, (50, 70), mask)

        draw.text((250, 35), "LEVEL UP", fill="white", font=font_big)
        draw.text((250, 100), user.display_name, fill="white", font=font_name)
        draw.text((250, 150), f"Level {level}", fill=(120, 220, 255), font=font_mid)
        draw.text((250, 185), get_rank(level), fill=(255, 200, 80), font=font_mid)
        draw.text((250, 220), get_title(level), fill=(200, 140, 255), font=font_mid)

        path = f"lvl_{user.id}.png"
        img.save(path)

        await channel.send(file=discord.File(path))
        os.remove(path)

    except Exception as e:
        print("CARD ERROR:", e)

# ---------------- XP HANDLER ----------------

async def handle_xp(user):
    try:
        data = await get_user(user.id)

        data["xp"] += random.randint(5, 15)

        while data["xp"] >= xp_needed(data["level"]):
            data["xp"] -= xp_needed(data["level"])
            data["level"] += 1
            await send_level_up(user, data["level"])

        await update_user(user.id, data["xp"], data["level"])

    except Exception as e:
        print("XP ERROR:", e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await handle_xp(message.author)
    await bot.process_commands(message)

# ---------------- ERROR ----------------

@bot.event
async def on_command_error(ctx, error):
    print("COMMAND ERROR:", repr(error))
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
    await send_level_up(member, level)

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

            async def callback(interaction, index=i):

                if interaction.user != self.players[self.turn]:
                    return await interaction.response.send_message("⛔ не твой ход", ephemeral=True)

                if self.board[index] != " ":
                    return await interaction.response.send_message("⛔ занято", ephemeral=True)

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

                new_view = TTT(self.players[0], self.players[1])
                new_view.board = self.board
                new_view.turn = self.turn
                new_view.build()

                await interaction.response.edit_message(
                    content=f"🎮 Ход: {self.players[self.turn].mention}",
                    view=new_view
                )

            btn.callback = callback
            self.add_item(btn)


@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)
    await ctx.send(f"🎮 {ctx.author.mention} vs {opponent.mention}", view=view)

# ---------------- FORTUNA ----------------

@bot.command(name="fortuna")
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

# ---------------- RUN ----------------

bot.run(os.getenv("TOKEN"))

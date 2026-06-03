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

    if not DATABASE_URL:
        print("❌ DATABASE_URL is missing")
        return

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

# ---------------- LEVEL SYSTEM ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    try:
        if db_pool:
            data = await get_user(message.author.id)

            data["xp"] += random.randint(5, 15)

            while data["xp"] >= xp_needed(data["level"]):
                data["xp"] -= xp_needed(data["level"])
                data["level"] += 1

            await update_user(message.author.id, data["xp"], data["level"])

    except Exception as e:
        print("XP ERROR:", e)

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

        if db_pool:
            data = await get_user(uid)

            data["xp"] += int(duration // 10)

            while data["xp"] >= xp_needed(data["level"]):
                data["xp"] -= xp_needed(data["level"])
                data["level"] += 1

            await update_user(uid, data["xp"], data["level"])

# ---------------- TTT GAME ----------------

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


# 🔥 ВОТ ГЛАВНЫЙ ФИКС ТВОЕЙ ПРОБЛЕМЫ
@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)
    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}",
        view=view
    )


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

    await ctx.send(f"🔮 {random.choice(choices)}")

# ---------------- START ----------------

@bot.event
async def setup_hook():
    await init_db()

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

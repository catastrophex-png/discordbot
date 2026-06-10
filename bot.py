import discord
from discord.ext import commands
import os
import random
import asyncio
import asyncpg

# ---------------- INTENTS ----------------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- SETTINGS ----------------

LEVEL_CHANNEL_ID = 1510080367892238336
AFK_CHANNEL_ID = 1510048410147749898

voice_activity = {}
voice_last_active = {}

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

AFK_EXEMPT_USERS = {1113722280573403156}

# ---------------- ORACLE ----------------

BRODYAGA_RESPONSES = [
    "🔮 Да",
    "🔥 Нет",
    "🌙 Возможно",
    "💀 Нет. И ты это знаешь.",
    "✨ Да. Но дорого обойдётся.",
]

# ---------------- ROLES ----------------

RANK_ROLES = {
    0: 1510087235184099338,
    1: 1510083478094352537,
    5: 1510083899458453505,
    10: 1510083942068260965,
    15: 1511756823219404821,
    20: 1510083995327795260,
    25: 1511756481710526694,
    30: 1511759108104130600,
    35: 1510084322370256896,
    40: 1510084249762660373,
    45: 1511756932992467137,
    50: 1510084369598124052,
    55: 1511756375485845674,
    60: 1511759454713024552,
    65: 1510085042951684206,
    70: 1511758939870597391,
    75: 1511759134058614874,
    80: 1511759165121368134,
    85: 1511761321388146848,
    90: 1511759362471891076,
    95: 1511755811062415502,
    100: 1511759410702057606,
    105: 1511759483670368276,
    110: 1511759537684615219,
    115: 1511759580378562681,
    120: 1511757185053360180
}

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

async def get_user(user_id):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xp, level FROM users WHERE user_id=$1",
            user_id
        )

        if not row:
            await conn.execute(
                "INSERT INTO users VALUES ($1, 0, 1)",
                user_id
            )
            return {"xp": 0, "level": 1}

        return {"xp": row["xp"], "level": row["level"]}

async def update_user(user_id, xp, level):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE SET xp=$2, level=$3
        """, user_id, xp, level)

# ---------------- XP ----------------

def xp_needed(level):
    return 75 + (level - 1) * 100

def bar(xp, need):
    size = 10
    p = xp / need
    return "█" * int(p * size) + "░" * (size - int(p * size))

def get_title(level):
    return f"LVL {level}"

async def level_up(member, data):
    while data["xp"] >= xp_needed(data["level"]):
        data["xp"] -= xp_needed(data["level"])
        data["level"] += 1

    await update_user(member.id, data["xp"], data["level"])

# ---------------- EVENTS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    data = await get_user(message.author.id)
    data["xp"] += random.randint(8, 18)

    await level_up(message.author, data)
    await update_user(message.author.id, data["xp"], data["level"])

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = member.id
    now = asyncio.get_event_loop().time()

    if after.channel and not before.channel:
        voice_activity[uid] = now

    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)
        if start:
            duration = now - start
            data = await get_user(uid)
            data["xp"] += int(duration // 60)
            await level_up(member, data)
            await update_user(uid, data["xp"], data["level"])

    # AFK SYSTEM
    if AFK_CHANNEL_ID and after.channel:
        afk_channel = member.guild.get_channel(AFK_CHANNEL_ID)
        if not afk_channel:
            return

        for m in after.channel.members:
            if m.bot:
                continue

            if m.id in AFK_EXEMPT_USERS:
                voice_last_active[m.id] = now
                continue

            last = voice_last_active.get(m.id, now)

            if now - last >= 900:
                try:
                    await m.move_to(afk_channel)
                    voice_last_active[m.id] = now
                except:
                    pass

        voice_last_active[uid] = now

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


class TTT(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=180)
        self.players = [p1, p2]
        self.board = [" "] * 9
        self.turn = 0
        self.buttons()

    def buttons(self):
        self.clear_items()

        for i in range(9):
            btn = discord.ui.Button(label="⬜", style=discord.ButtonStyle.secondary, row=i // 3)

            async def callback(interaction, index=i):
                if interaction.user != self.players[self.turn]:
                    return await interaction.response.send_message("Не твой ход", ephemeral=True)

                if self.board[index] != " ":
                    return await interaction.response.send_message("Занято", ephemeral=True)

                self.board[index] = "❌" if self.turn == 0 else "⭕"

                winner = check(self.board)

                if winner:
                    for b in self.children:
                        b.disabled = True
                    return await interaction.response.edit_message(
                        content=f"🏆 Победил {interaction.user.mention}",
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

                await interaction.response.edit_message(
                    content=f"Ход: {self.players[self.turn].mention}",
                    view=new_view
                )

            btn.callback = callback
            self.add_item(btn)

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    await ctx.send(f"🎮 {ctx.author.mention} vs {opponent.mention}", view=TTT(ctx.author, opponent))

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
        f"⭐ Level: {data['level']}\n"
        f"`{bar(data['xp'], xp_needed(data['level']))}`\n"
        f"{data['xp']}/{xp_needed(data['level'])}"
    )

@bot.command(name="фортуна")
async def fortuna(ctx):
    choices = []

    await ctx.send("Вводи варианты, напиши 'готово'")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        msg = await bot.wait_for("message", check=check)
        if msg.content.lower() == "готово":
            break
        choices.append(msg.content)

    await ctx.send(random.choice(choices) if choices else "пусто")

@bot.command(name="бродяга")
async def brodyaga(ctx, *, question=None):
    if not question:
        return await ctx.send("нет вопроса")

    await ctx.send(random.choice(BRODYAGA_RESPONSES))

# ---------------- START ----------------

@bot.event
async def setup_hook():
    await init_db()

@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

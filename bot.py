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
voice_activity = {}

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

# ---------------- ROLES ----------------

RANK_ROLES = {
    0: 1510087235184099338,
    1: 1510083478094352537,
    5: 1510083899458453505,
    10: 1510083942068260965,
    15: 1510083995327795260,
    20: 1510084249762660373,
    25: 1510084322370256896,
    30: 1510084369598124052,
    40: 1510085042951684206
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
                "INSERT INTO users (user_id, xp, level) VALUES ($1, 0, 1)",
                user_id
            )
            return {"xp": 0, "level": 1}

        return {"xp": row["xp"], "level": row["level"]}

async def update_user(user_id, xp, level):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id, xp, level)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id)
        DO UPDATE SET xp=$2, level=$3
        """, user_id, xp, level)

# ---------------- XP ----------------

def xp_needed(level):
    return 75 + (level - 1) * 100

def bar(xp, need):
    size = 10
    p = xp / need
    return "█" * int(p * size) + "░" * (size - int(p * size))

def get_title(level):
    if level < 1: return "Ноунейм"
    if level < 5: return "Личинус"
    if level < 10: return "Бывалый"
    if level < 15: return "На опыте"
    if level < 20: return "Пизделка"
    if level < 25: return "Пиздец"
    if level < 30: return "Ебланище"
    if level < 40: return "Животное"
    return "Легенда сервера"

def get_role(level):
    keys = sorted(RANK_ROLES.keys())
    chosen = 0
    for k in keys:
        if level >= k:
            chosen = k
    return RANK_ROLES[chosen]

async def update_roles(member, level):
    role_id = get_role(level)
    role = member.guild.get_role(role_id)
    if not role:
        return

    all_roles = [member.guild.get_role(r) for r in RANK_ROLES.values()]
    all_roles = [r for r in all_roles if r]

    await member.remove_roles(*[r for r in member.roles if r in all_roles])
    await member.add_roles(role)

async def level_up(member, data):
    leveled = False

    while data["xp"] >= xp_needed(data["level"]):
        data["xp"] -= xp_needed(data["level"])
        data["level"] += 1
        leveled = True

    if not leveled:
        return

    await update_user(member.id, data["xp"], data["level"])
    await update_roles(member, data["level"])

    channel = bot.get_channel(LEVEL_CHANNEL_ID)

    if channel:
        await channel.send(
            f"🎉 Новый уровень!\n\n"
            f"👤 {member.mention}\n"
            f"⭐ Уровень: {data['level']}\n"
            f"🏅 Роль: {get_title(data['level'])}\n"
            f"`{bar(data['xp'], xp_needed(data['level']))}` "
            f"{data['xp']}/{xp_needed(data['level'])}"
        )

# ---------------- EVENTS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if db_pool:
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

    if after.channel and not before.channel:
        voice_activity[uid] = asyncio.get_event_loop().time()

    elif before.channel and not after.channel:
        start = voice_activity.pop(uid, None)
        if not start:
            return

        duration = asyncio.get_event_loop().time() - start

        if db_pool:
            data = await get_user(uid)
            data["xp"] += int(duration // 60)

            await level_up(member, data)
            await update_user(uid, data["xp"], data["level"])

# ---------------- TTT (ТВОЯ ИГРА ВОЗВРАЩЕНА) ----------------

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
        super().__init__()
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
                    return await interaction.response.send_message("⛔ Не твой ход", ephemeral=True)

                if self.board[index] != " ":
                    return await interaction.response.send_message("⛔ Уже занято", ephemeral=True)

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

                await interaction.response.edit_message(
                    content=f"🎮 Ход: {self.players[self.turn].mention}",
                    view=new_view
                )

            btn.callback = callback
            self.add_item(btn)


@bot.command()
async def ttt(ctx, opponent: discord.Member):
    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}",
        view=TTT(ctx.author, opponent)
    )

# ---------------- COMMANDS ----------------

@bot.command()
async def ping(ctx):
    await ctx.send("pong")


@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user(member.id)

    await ctx.send(
        f"📊 {member.display_name}\n\n"
        f"⭐ Уровень: {data['level']}\n"
        f"🏅 Роль: {get_title(data['level'])}\n"
        f"`{bar(data['xp'], xp_needed(data['level']))}`\n"
        f"{data['xp']}/{xp_needed(data['level'])}"
    )


@bot.command(name="фортуна")
async def fortuna(ctx):
    choices = []

    await ctx.send("🔮 Вводи варианты, напиши 'готово'")

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

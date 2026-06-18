import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
import asyncpg
from discord import ui

# ---------------- INTENTS ----------------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- SETTINGS ----------------

LEVEL_CHANNEL_ID = 1510080367892238336

voice_activity = {}
voice_last_active = {}
voice_join_time = {}
afk_members = set()

AFK_TIMEOUT = 900  # 15 минут

AFK_EXEMPT_USERS = {
    1113722280573403156
}

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

# ---------------- ORACLE: БРОДЯГА ----------------

BRODYAGA_RESPONSES = [
    "🔮 Бродяга молчит…",
    "✨ Да. Но ты поймёшь это слишком поздно.",
    "⚠️ Нет. И судьба уже закрыла эту дверь.",
    "🌙 Возможно… если не свернёшь с пути.",
    "🕯️ Ответ спрятан в том, что ты игнорируешь.",
    "🔥 Да, но цена тебе не понравится.",
    "🌫️ Вернись позже.",
    "👁️ Я вижу движение… но не вижу тебя в конце пути.",
    "💀 Нет. И ты это уже чувствуешь.",
    "🌟 Да. Без сомнений и без жалости.",
    "🌀 Всё возможно, но ты сам мешаешь исходу.",
    "📿 Ответ очевиден, если бы ты смотрел.",
    "🔮 Не отвлекай меня от смысла жизни.",
    "✨ Да. Но только если ты перестанешь делать то, что делаешь сейчас.",
    "⚠️ Нет. Даже чайник вскипает быстрее, чем это случится.",
    "🌙 Вселенная пока занята более интересными людьми.",
    "🕯️ Ответ спрятан. Я тоже не знаю где.",
    "🔥 Да, но потом ты пожалеешь и скажешь 'почему я спросил'.",
    "🌫️ Сейчас будущее занято. Попробуй позже, оно в отпуске.",
    "👁️ Я вижу… что ты снова задаёшь странные вопросы.",
    "💀 Нет. Даже если очень попросишь.",
    "🌟 Да. Но это подозрительно и я бы тебе не доверял.",
    "🌀 Всё возможно, но ты выбрал самый странный таймлайн.",
    "📿 *Бродяга вздыхает* ",
    "🍺 Будущее сейчас недоступно.",
    "🐌 Да… но улитка уже успела бы три раза дойти быстрее.",
    "🧠 Ты уже знаешь ответ.",
    "🚪 Ответ есть. Но он ушёл и закрыл за собой дверь.",
    "🔮 Бродяга долго думает… и решает, что ты справишься сам.",
    "✨ Да. Но только если не будешь мешать вселенной своими вопросами.",
    "⚠️ Нет. И честно, это даже к лучшему для всех.",
    "🌙 Возможно…",
    "🕯️ Мне впадлу.",
    "🔥 Да, но потом ты будешь делать вид, что это была не твоя идея.",
    "🌫️ Тебя игнорируют.",
    "👁️ Ты снова спрашиваешь что-то странное.",
    "💀 Не задавай этот вопрос мне стыдно за тебя.",
    "🌀 Всё возможно…",
    "💀 Нет.",
    "🔥 Да. ",
    
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
    if level < 20: return "Роняли вниз головой"
    if level < 25: return "Пизделка"
    if level < 30: return "Ошибка природы"
    if level < 35: return "Пиздец"
    if level < 40: return "Ебланище"
    if level < 45: return "Бомж"
    if level < 50: return "Абортыш"
    if level < 55: return "Животное"
    if level < 60: return "Психушка"
    if level < 65: return "Нехуй делать"
    if level < 70: return "Легенда сервера"
    if level < 75: return "Монстр"
    if level < 80: return "Страпёр"
    if level < 85: return "Завсегдатый"
    if level < 90: return "Голос сервера"
    if level < 95: return "Пробужденный"
    if level < 100: return "Неуязвимый"
    if level < 105: return "Ошибка системы"
    if level < 110: return "Неприкасаемый"
    if level < 115: return "Финальный босс"
    if level < 120: return "Босс толчка"
    return "Мелстрой"

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

async def level_up(member, old_level, data):
    channel = bot.get_channel(LEVEL_CHANNEL_ID)
    if not channel:
        return False

    new_level = data["level"]  # 👈 фиксируем явно

    need = xp_needed(new_level)
    progress = bar(data["xp"], need)

    embed = discord.Embed(
        title="🎉 Level Up!",
        description=f"У {member.mention} новый уровень. Пиздец 🔥",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="✨🔥🎁 Уровень",
        value=f"`{old_level}` ➜ `{data['level']}`",
        inline=False
    )

    embed.add_field(
        name="🏆🏅🃏 Титул",
        value=get_title(data["level"]),
        inline=False
    )

    embed.add_field(
        name="📒📝💼 XP",
        value=f"{data['xp']}/{need}",
        inline=False
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Иди нахуй и продолжай активность 💪")

    await channel.send(embed=embed)

    return True
        
# ---------------- EVENTS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    xp_gain = random.randint(5, 15)

    data = await get_user(message.author.id)

    old_level = data["level"]

    data["xp"] += xp_gain
    data["xp"], data["level"] = recalc_level(data["xp"], data["level"])

    await update_user(message.author.id, data["xp"], data["level"])
    await update_roles(message.author, data["level"])

    if data["level"] > old_level:
        await level_up(message.author, old_level, data)
    
    await bot.process_commands(message)
    
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    uid = member.id
    now = asyncio.get_event_loop().time()

    # вошёл в голос
    if before.channel is None and after.channel is not None:
        voice_join_time[uid] = now

    # вышел из голосового
    elif before.channel is not None and after.channel is None:
        if uid not in voice_join_time:
            return

        duration = now - voice_join_time[uid]
        del voice_join_time[uid]

        xp_gain = int(duration // 60) * 8

        if xp_gain <= 0:
            return

        data = await get_user(uid)

        old_level = data["level"]

        data["xp"] += xp_gain
        data["xp"], data["level"] = recalc_level(data["xp"], data["level"])

        await update_user(uid, data["xp"], data["level"])
        await update_roles(member, data["level"])

    if data["level"] > old_level:
        await level_up(member, old_level, data)
# ---------------- AFK LOOP ----------------

@tasks.loop(minutes=1)
async def check_afk():
    now = asyncio.get_event_loop().time()

    for guild in bot.guilds:
        afk_channel = guild.afk_channel

        if not afk_channel:
            continue

        for vc in guild.voice_channels:
            if vc == afk_channel:
                continue

            for member in vc.members:
                if member.bot:
                    continue

                if member.id in AFK_EXEMPT_USERS:
                    continue

                if not member.voice:
                    continue

                if not (member.voice.self_mute or member.voice.self_deaf):
                    continue

                last = voice_last_active.get(member.id)

                if last and now - last >= AFK_TIMEOUT:
                    try:
                        await member.move_to(afk_channel)
                        afk_members.add(member.id)
                        voice_last_active[member.id] = now
                    except:
                        pass
                        
# ------------- LEVEL SYSTEM HELPERS -------------

def recalc_level(xp, level):

    while xp >= xp_needed(level):
        xp -= xp_needed(level)
        level += 1

    while xp < 0 and level > 1:
        level -= 1
        xp += xp_needed(level)

    if level == 1 and xp < 0:
        xp = 0

    return xp, level
    
# ------------- ROULETTE VIEW -------------

class RouletteView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user = user
        self.bullets = 0
        self.reward = 0
        self.penalty = 0

    # ---------------- DIFFICULTY ----------------

    @discord.ui.button(label="🟢 Изи", style=discord.ButtonStyle.success)
    async def easy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 1, 10, -10)

    @discord.ui.button(label="🟠 Мид", style=discord.ButtonStyle.primary)
    async def mid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 3, 30, -30)

    @discord.ui.button(label="🔴 Безумие", style=discord.ButtonStyle.danger)
    async def hard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 6, 120, -60)

    # ---------------- START GAME ----------------

    async def start(self, interaction: discord.Interaction, b, r, p):
        if interaction.user != self.user:
            return await interaction.response.send_message("⛔ руки убрал", ephemeral=True)

        self.bullets = b
        self.reward = r
        self.penalty = p

        self.clear_items()
        self.add_item(self.shoot_button())
        self.add_item(self.pass_button())

        await interaction.response.edit_message(
            content="🔫 Барабан заряжен. Выбирай :",
            view=self
        )

    # ---------------- SHOOT ----------------

    def shoot_button(self):
        button = discord.ui.Button(label="💥 Выстрел", style=discord.ButtonStyle.danger)

        async def callback(interaction: discord.Interaction):
            if interaction.user != self.user:
                return await interaction.response.send_message("⛔ руки убрал", ephemeral=True)

            await interaction.response.defer()

            roll = random.randint(1, 7)
            data = await get_user(interaction.user.id)

            old_level = data["level"]

            if roll <= self.bullets:
                delta = self.penalty
                result = "💀 БАХ! Ты проиграл, судьба не была к тебе благосклонна."
            else:
                delta = self.reward
                result = "😮 Ебать, ты выжил"

            data["xp"] += delta

            data["xp"], data["level"] = recalc_level(
                data["xp"],
                data["level"]
            )

            await update_user(interaction.user.id, data["xp"], data["level"])

            await update_roles(interaction.user, data["level"])

            await interaction.message.edit(
                content=(
                    f"🎰 Игра окончена\n\n"
                    f"👤 {interaction.user.mention}\n"
                    f"📊 XP: {delta:+}\n"
                    f"⭐ {old_level} → {data['level']}\n"
                    f"🏁 {data['xp']}/{xp_needed(data['level'])}\n\n"
                    f"{result}"
                ),
                view=None
            )

        button.callback = callback
        return button

    # ---------------- PASS ----------------

    def pass_button(self):
        button = discord.ui.Button(label="🚪 Пас", style=discord.ButtonStyle.secondary)

        async def callback(interaction: discord.Interaction):
            if interaction.user != self.user:
                return await interaction.response.send_message("⛔ руки убрал", ephemeral=True)

            await interaction.response.defer()

            await interaction.message.edit(
                content="🚪 Ты вышел из игры и живёшь дальше, ссыкло",
                view=None
            )

        button.callback = callback
        return button
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
                    return await interaction.response.send_message("⛔ Эй псина, не твой ход", ephemeral=True)

                if self.board[index] != " ":
                    return await interaction.response.send_message("⛔ Занято нахуй", ephemeral=True)

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

                await interaction.message.edit(
                    content=f"🎮 Ход: {self.players[self.turn].mention}",
                    view=new_view
                )

            btn.callback = callback
            self.add_item(btn)

@bot.command(name="кн")
async def ttt(ctx, opponent: discord.Member):
    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}",
        view=TTT(ctx.author, opponent)
    )

# ---------------- COMMANDS ----------------

@bot.command(name="пинг")
async def ping(ctx):
    await ctx.send("понг")

@bot.command(name="ранг")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user(member.id)

    await ctx.send(
        f"📊 {member.display_name}\n\n"
        f"⭐ Уровень: {data['level']}\n"
        f"🏅 Роль: {get_title(data['level'])}\n"
        f"{bar(data['xp'], xp_needed(data['level']))}\n"
        f"{data['xp']}/{xp_needed(data['level'])}"
    )

# 🔮 БРОДЯГА (ОРАКУЛ)

@bot.command(name="бродяга")
async def brodyaga(ctx, *, question=None):
    if not question:
        return await ctx.send("🔮 Бродяга ждёт вопроса…")

    answer = random.choice(BRODYAGA_RESPONSES)

    await ctx.send(
        f"🔮 **Бродяга предсказывает:** {question}\n\n"
        f"{answer}"
    )

@bot.command(name="фортуна")
async def fortuna(ctx):
    choices = []
    await ctx.send("🔮 Вводи варианты (каждый в своём сообщении), потом напиши: готово")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        msg = await bot.wait_for("message", check=check)
        if msg.content.lower() == "готово":
            break
        choices.append(msg.content)

    if not choices:
        return await ctx.send("❌ нет вариков")

    await ctx.send(f"🔮 {random.choice(choices)}")

@bot.command()
async def рулетка(ctx):
    view = RouletteView(ctx.author)

    await ctx.send(
        "🔫 Рулетка\n\n"
        "Выбери уровень риска:\n\n"
        "🟢 Изи — 1 из 7 (+10 / -10)\n"
        "🟠 Мид — 3 из 7 (+30 / -30)\n"
        "🔴 Безумие — 6 из 7 (+120 / -60)\n",
        view=view
    )

# ---------------- START ----------------

@bot.event
async def setup_hook():
    await init_db()

@bot.event
async def on_ready():
    if not check_afk.is_running():
        check_afk.start()

    print("BOT ONLINE:", bot.user)

bot.run(os.getenv("TOKEN"))

import discord
from discord.ext import commands
import os
import random

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- КРЕСТИКИ-НОЛИКИ ---

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

        for i in range(9):
            self.add_item(self.make_button(i))

    def make_button(self, i):
        mark = self.board[i]
        label = mark if mark != " " else "⬜"

        btn = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=i // 3,
            disabled=(mark != " ")
        )

        async def callback(interaction: discord.Interaction):
            if interaction.user != self.players[self.turn]:
                return await interaction.response.send_message("Эй псина, не твой ход", ephemeral=True)

            if self.board[i] != " ":
                return await interaction.response.send_message("Занято нахуй", ephemeral=True)

            self.board[i] = "❌" if self.turn == 0 else "⭕"

            winner = check(self.board)

            if winner:
                view = TTT(self.players[0], self.players[1], self.board, self.turn)
                for b in view.children:
                    b.disabled = True

                return await interaction.response.edit_message(
                    content=f"🏆 Победитель: {interaction.user.mention}",
                    view=view
                )

            if " " not in self.board:
                view = TTT(self.players[0], self.players[1], self.board, self.turn)
                for b in view.children:
                    b.disabled = True

                return await interaction.response.edit_message(
                    content="🤝 Ничья",
                    view=view
                )

            next_turn = 1 - self.turn
            view = TTT(self.players[0], self.players[1], self.board, next_turn)

            await interaction.response.edit_message(
                content=f"Ход: {view.players[view.turn].mention}",
                view=view
            )

        btn.callback = callback
        return btn


# --- ФОРТУНА ---

@bot.command(name="фортуна")
async def fortuna(ctx):
    await ctx.send(
        "🔮 **Фортуна запущена!**\n"
        "Отправляй варианты по одному сообщению.\n"
        "Когда закончишь — напиши **готово**"
    )

    variants = []

    def check_msg(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while True:
        try:
            msg = await bot.wait_for("message", check=check_msg, timeout=300)

            if msg.content.lower().strip() == "готово":
                break

            variants.append(msg.content.strip())

        except:
            await ctx.send("⌛ Время вышло.")
            return

    if not variants:
        await ctx.send("❌ Ты не добавила варианты.")
        return

    await ctx.send(
        "🔮 Варианты:\n\n" +
        "\n".join(f"• {v}" for v in variants) +
        "\n\n🎲 Кручу..."
    )

    winner = random.choice(variants)

    await ctx.send(f"✨ Победитель: **{winner}** ✨")


# --- TTT команда ---

@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)

    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}\n"
        f"Ход: {view.players[view.turn].mention}",
        view=view
    )


# --- ping ---

@bot.command()
async def ping(ctx):
    await ctx.send("бот жив 🟢")


@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(os.getenv("TOKEN"))

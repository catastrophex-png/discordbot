import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
        super().__init__(timeout=None)

        self.board = [" "] * 9
        self.players = [p1, p2]
        self.turn = 0

        for i in range(9):
            self.add_item(self.make_button(i))

    def make_button(self, i):
        btn = discord.ui.Button(
            label="⬜",
            style=discord.ButtonStyle.secondary,
            row=i // 3
        )

        async def callback(interaction):
            if interaction.user != self.players[self.turn]:
                return await interaction.response.send_message("Не твой ход", ephemeral=True)

            if self.board[i] != " ":
                return await interaction.response.send_message("Уже занято", ephemeral=True)

            mark = "❌" if self.turn == 0 else "⭕"
            self.board[i] = mark

            btn.label = mark
            btn.disabled = True

            winner = check(self.board)

            if winner:
                for c in self.children:
                    c.disabled = True

                return await interaction.response.edit_message(
                    content=f"🏆 Победитель: {interaction.user.mention}",
                    view=self
                )

            if " " not in self.board:
                for c in self.children:
                    c.disabled = True

                return await interaction.response.edit_message(
                    content="🤝 Ничья",
                    view=self
                )

            self.turn = 1 - self.turn

            await interaction.response.edit_message(
                content=self.draw(),
                view=self
            )

        btn.callback = callback
        return btn

    def draw(self):
        b = self.board
        return f"""
{b[0]} ┃ {b[1]} ┃ {b[2]}
━━━╋━━━╋━━━
{b[3]} ┃ {b[4]} ┃ {b[5]}
━━━╋━━━╋━━━
{b[6]} ┃ {b[7]} ┃ {b[8]}
"""


@bot.command()
async def ttt(ctx, opponent: discord.Member):
    game = TTT(ctx.author, opponent)
    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}",
        view=game
    )


@bot.command()
async def ping(ctx):
    await ctx.send("бот жив 🟢")


@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(os.getenv("TOKEN"))

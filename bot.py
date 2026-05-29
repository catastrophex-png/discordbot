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


def render(board):
    b = board
    return f"""
{b[0]} ┃ {b[1]} ┃ {b[2]}
━━━╋━━━╋━━━
{b[3]} ┃ {b[4]} ┃ {b[5]}
━━━╋━━━╋━━━
{b[6]} ┃ {b[7]} ┃ {b[8]}
"""


class TTT(discord.ui.View):
    def __init__(self, p1, p2, board=None, turn=0):
        super().__init__(timeout=None)

        self.players = [p1, p2]
        self.board = board or [" "] * 9
        self.turn = turn

        # создаём кнопки заново КАЖДЫЙ РАЗ (ВАЖНО)
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

        async def callback(interaction):
            if interaction.user != self.players[self.turn]:
                return await interaction.response.send_message("Не твой ход", ephemeral=True)

            if self.board[i] != " ":
                return await interaction.response.send_message("Уже занято", ephemeral=True)

            # обновляем состояние
            self.board[i] = "❌" if self.turn == 0 else "⭕"

            winner = check(self.board)

            # победа
            if winner:
                new_view = TTT(self.players[0], self.players[1], self.board, self.turn)

                for child in new_view.children:
                    child.disabled = True

                return await interaction.response.edit_message(
                    content=f"🏆 Победитель: {interaction.user.mention}\n\n{render(self.board)}",
                    view=new_view
                )

            # ничья
            if " " not in self.board:
                new_view = TTT(self.players[0], self.players[1], self.board, self.turn)

                for child in new_view.children:
                    child.disabled = True

                return await interaction.response.edit_message(
                    content=f"🤝 Ничья\n\n{render(self.board)}",
                    view=new_view
                )

            # следующий ход (ВАЖНО: создаём новый view)
            next_turn = 1 - self.turn
            new_view = TTT(self.players[0], self.players[1], self.board, next_turn)

            await interaction.response.edit_message(
                content=render(self.board),
                view=new_view
            )

        btn.callback = callback
        return btn


@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)

    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}\n\n{render(view.board)}",
        view=view
    )


@bot.command()
async def ping(ctx):
    await ctx.send("бот жив 🟢")


@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(os.getenv("TOKEN"))

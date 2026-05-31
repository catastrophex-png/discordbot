```python
import discord
from discord.ext import commands
import os
import random

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
                return await interaction.response.send_message(
                    "Эй псина, не твой ход",
                    ephemeral=True
                )

            if self.board[i] != " ":
                return await interaction.response.send_message(
                    "Занято нахуй",
                    ephemeral=True
                )

            self.board[i] = "❌" if self.turn == 0 else "⭕"

            winner = check(self.board)

            if winner:
                new_view = TTT(self.players[0], self.players[1], self.board, self.turn)
                for child in new_view.children:
                    child.disabled = True

                return await interaction.response.edit_message(
                    content=f"🏆 Победитель: {interaction.user.mention}",
                    view=new_view
                )

            if " " not in self.board:
                new_view = TTT(self.players[0], self.players[1], self.board, self.turn)
                for child in new_view.children:
                    child.disabled = True

                return await interaction.response.edit_message(
                    content="🤝 Ничья",
                    view=new_view
                )

            next_turn = 1 - self.turn
            new_view = TTT(self.players[0], self.players[1], self.board, next_turn)

            await interaction.response.edit_message(
                content=f"Ход: {new_view.players[new_view.turn].mention}",
                view=new_view
            )

        btn.callback = callback
        return btn


@bot.command(name="фортуна")
async def fortuna(ctx):
    await ctx.send(
        "🔮 **Режим Фортуны запущен!**\n"
        "Отправляйте варианты по одному сообщению.\n"
        "Когда закончите, напишите: **готово**"
    )

    variants = []

    def msg_check(message):
        return (
            message.author == ctx.author
            and message.channel == ctx.channel
        )

    while True:
        try:
            msg = await bot.wait_for(
                "message",
                check=msg_check,
                timeout=300
            )

            if msg.content.lower().strip() == "готово":
                break

            variants.append(msg.content.strip())

        except:
            await ctx.send("⌛ Время ожидания истекло.")
            return

    if not variants:
        await ctx.send("❌ Вы не добавили ни одного варианта.")
        return

    text = "\n".join(f"• {v}" for v in variants)

    await ctx.send(
        f"🔮 **Варианты собраны:**\n\n{text}\n\n🎲 Крутим колесо..."
    )

    winner = random.choice(variants)

    await ctx.send(
        f"🥁🥁🥁\n"
        f"✨ **Победитель: {winner}** ✨"
    )


@bot.command()
async def ttt(ctx, opponent: discord.Member):
    view = TTT(ctx.author, opponent)

    await ctx.send(
        f"🎮 {ctx.author.mention} vs {opponent.mention}\n"
        f"Ход: {view.players[view.turn].mention}",
        view=view
    )


@bot.command()
async def ping(ctx):
    await ctx.send("бот жив 🟢")


@bot.event
async def on_ready():
    print("BOT ONLINE:", bot.user)


bot.run(os.getenv("TOKEN"))
```

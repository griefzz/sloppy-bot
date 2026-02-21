import asyncio

import discord
from discord.ext import commands

from config.settings import settings

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user} has logged in!")


async def main():
    async with bot:
        await bot.load_extension("cogs.images")
        await bot.load_extension("cogs.vision")
        await bot.load_extension("cogs.video")
        await bot.load_extension("cogs.admin")
        await bot.start(settings.discord_token)


settings.validate()
asyncio.run(main())

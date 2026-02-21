import os
import subprocess
import sys

import discord
from discord.ext import commands

import error_log as error_log_module


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def wtfhappen(self, ctx: commands.Context):
        """Show recent error log."""
        if not error_log_module.error_log:
            await ctx.reply("No errors logged since last restart.")
            return
        lines = list(error_log_module.error_log)
        header = f"**Last {len(lines)} error(s) since restart:**\n```\n"
        footer = "\n```"
        body = ""
        for entry in reversed(lines):
            candidate = entry + "\n"
            if len(header) + len(body) + len(candidate) + len(footer) > 1990:
                break
            body = candidate + body
        await ctx.reply(f"{header}{body}{footer}")

    @commands.command()
    async def update(self, ctx: commands.Context):
        """Pull latest code from git and restart the bot.

        Usage: /update
        Only the bot owner can use this command.
        """
        status_msg = await ctx.reply("Pulling latest changes...")
        try:
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() or result.stderr.strip()
            if "Already up to date" in (result.stdout or ""):
                await status_msg.edit(content="Already up to date. No restart needed.")
                return
            await status_msg.edit(content=f"```\n{output}\n```\nRestarting...")
        except Exception as e:
            await status_msg.edit(content=f"Git pull failed: {e}")
            return

        await self.bot.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @commands.command()
    async def help_bot(self, ctx: commands.Context):
        """Show help information for the bot commands."""
        embed = discord.Embed(title="🤖 Bot Commands Help", color=0x0099FF)

        embed.add_field(
            name="/flux <text>",
            value="Generate an image using Flux Fast\n• Example: `/flux a cat wearing sunglasses`",
            inline=False,
        )
        embed.add_field(
            name="/nana <text>",
            value="Generate an image using Google Nano Banana (Gemini Flash)\n• Example: `/nana a tropical sunset`",
            inline=False,
        )
        embed.add_field(
            name="/zimg <text>",
            value="Generate an image using Z-Image Turbo (1920x1080)\n• Example: `/zimg a mountain landscape`",
            inline=False,
        )
        embed.add_field(
            name="/blip [question]",
            value="Caption or ask about an attached image (BLIP)\n• Example: `/blip` or `/blip what color is the car?`",
            inline=False,
        )
        embed.add_field(
            name="/qwen [question]",
            value="Ask about an attached image or video (Qwen3-VL)\n• Example: `/qwen` or `/qwen what is happening here?`",
            inline=False,
        )
        embed.add_field(
            name="/caption [question]",
            value="Caption or ask about an attached image (Moondream2)\n• Example: `/caption what is in this photo?`",
            inline=False,
        )
        embed.add_field(
            name="/seed <text>",
            value="Generate a 5s video using Seedance 1 Lite (480p)\n• Attach 1 image for first frame, 2 for first+last\n• Example: `/seed a dog running on the beach`",
            inline=False,
        )
        embed.add_field(name="/wtfhappen", value="Show recent error log", inline=False)
        embed.add_field(name="/help_bot", value="Show this help message", inline=False)

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))

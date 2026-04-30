import asyncio
import os
import subprocess
import sys
from io import BytesIO
from urllib.parse import urlparse

from cogs.utils import unwrap_output

import discord
import replicate
import requests
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
    async def gimme(self, ctx: commands.Context, n: int = 0):
        """Re-post the Nth most recent succeeded Replicate prediction.

        Usage: /gimmi      (latest)
               /gimmi 0    (latest)
               /gimmi 1    (second latest)
        """
        try:
            async with ctx.typing():
                page = await asyncio.to_thread(replicate.predictions.list)
                succeeded = [p for p in page if p.status == "succeeded" and p.output]
                if n >= len(succeeded):
                    await ctx.reply(f"Only {len(succeeded)} succeeded prediction(s) available.")
                    return
                prediction = succeeded[n]
                if not prediction:
                    await ctx.reply("No recent succeeded predictions found.")
                    return

                url = unwrap_output(prediction.output)
                response = await asyncio.to_thread(
                    requests.get, url, timeout=(10, 120)
                )
                content_type = response.headers.get("Content-Type", "")
                ext = os.path.splitext(urlparse(url).path)[1] or (
                    ".mp4" if "video" in content_type else
                    ".flac" if "audio" in content_type else
                    ".jpg"
                )
                data = BytesIO(response.content)
                if data.getbuffer().nbytes > 25 * 1024 * 1024:
                    await ctx.reply(f"File too large for Discord. URL:\n{url}")
                    return
                data.seek(0)
                await ctx.reply(file=discord.File(data, f"output{ext}"))
        except Exception as e:
            await ctx.reply(f"❌ An error occurred: {e}")

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
            value="Generate an image using Google Nano Banana (Gemini Flash)\n• Attach or reply with images for reference\n• Example: `/nana a tropical sunset`",
            inline=False,
        )
        embed.add_field(
            name="/zimg <text>",
            value="Generate an image using Z-Image Turbo (1920x1080)\n• Example: `/zimg a mountain landscape`",
            inline=False,
        )
        embed.add_field(
            name="/pimg <text>",
            value="Edit images using P-Image-Edit\n• Attach 1-5 images or reply to a message with an image\n• Example: `/pimg make the sky purple`",
            inline=False,
        )
        embed.add_field(
            name="/qwen <text>",
            value="Edit images using Qwen Image Edit Plus\n• Attach 1-3 images or reply to a message with an image\n• Example: `/qwen remove the background`",
            inline=False,
        )
        embed.add_field(
            name="/blip [question]",
            value="Caption or ask about an image (BLIP)\n• Attach or reply with an image\n• Example: `/blip` or `/blip what color is the car?`",
            inline=False,
        )
        embed.add_field(
            name="/caption [question]",
            value="Caption or ask about an image (Moondream2)\n• Attach or reply with an image\n• Example: `/caption what is in this photo?`",
            inline=False,
        )
        embed.add_field(
            name="/seed <text>",
            value="Generate a 5s video using Seedance 1 Pro Fast (480p)\n• Attach/reply with 1 image for first frame, 2 for first+last\n• Example: `/seed a dog running on the beach`",
            inline=False,
        )
        embed.add_field(
            name="/pvid <text>",
            value="Generate a video using P-Video (720p)\n• Attach/reply with an image for image-to-video\n• Example: `/pvid waves crashing on rocks`",
            inline=False,
        )
        embed.add_field(
            name="/zpvid <text>",
            value="Like /pvid but with prompt_upsampling disabled (raw prompt)\n• Example: `/zpvid waves crashing on rocks`",
            inline=False,
        )
        embed.add_field(
            name="/continue [text]",
            value="Continue a /seed video using its last frame\n• Reply to a bot video with `/continue` (reuses original prompt)\n• Or `/continue new prompt` to steer the continuation",
            inline=False,
        )
        embed.add_field(
            name="/mmaudio [text]",
            value="Generate audio using MMAudio\n• Attach/reply with a video for video-to-audio\n• Example: `/mmaudio wind blowing through trees`",
            inline=False,
        )
        embed.add_field(
            name="/gimme [n]",
            value="Re-post the Nth most recent Replicate output\n• Example: `/gimme` (latest) or `/gimme 2` (3rd latest)",
            inline=False,
        )
        embed.add_field(name="/help_bot", value="Show this help message", inline=False)

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))

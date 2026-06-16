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
            name="/grok <text>",
            value="Generate or edit images using xAI Grok Imagine (2k, 16:9)\n• No attachment: text-to-image\n• Attach 1-3 images or reply with an image: edit mode\n• Example: `/grok a futuristic city at night`",
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
            value="Generate or edit images using P-Image\n• No attachment: text-to-image\n• Attach 1-5 images or reply with an image: edit mode\n• Example: `/pimg a cat wearing sunglasses` or `/pimg make the sky purple`",
            inline=False,
        )
        embed.add_field(
            name="/qwen <text>",
            value="Generate or edit images using Qwen Image\n• No attachment: text-to-image\n• Attach 1-3 images or reply with an image: edit mode\n• Example: `/qwen a futuristic city` or `/qwen remove the background`",
            inline=False,
        )
        embed.add_field(
            name="/ideo <text>",
            value="Generate an image using Ideogram v4 Turbo (2560x1440, 16:9)\n• Example: `/ideo a surreal landscape with floating islands`",
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
            value="Generate a video using P-Video (720p)\n• Attach 1 image for first frame, 2 for first+last\n• Example: `/pvid waves crashing on rocks`",
            inline=False,
        )
        embed.add_field(
            name="/zpvid <text>",
            value="Like /pvid but with prompt_upsampling disabled (raw prompt)\n• Attach 1 image for first frame, 2 for first+last\n• Example: `/zpvid waves crashing on rocks`",
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
        embed.add_field(name="/cost", value="Show approximate cost per run for each command", inline=False)

        await ctx.reply(embed=embed)

    @commands.command()
    async def cost(self, ctx: commands.Context):
        """Show approximate Replicate cost per run for each command (as of 5/29/2026).

        Usage: /cost
        """
        embed = discord.Embed(
            title="Approximate costs per run (as of 5/29/2026)",
            description="Based on default settings. Variable-rate models show the typical run cost.",
            color=0x0099FF,
        )
        embed.add_field(name="/flux",    value="~$0.005  — prunaai/flux-fast (200 runs/$1)", inline=False)
        embed.add_field(name="/grok",    value="~$0.02  — xai/grok-imagine-image (2k, 16:9)", inline=False)
        embed.add_field(name="/flux2",   value="$0.002/input MP + $0.015/output MP  — black-forest-labs/flux-2-klein-9b\nText-to-image (1MP out): ~$0.015 | Image-to-image: +$0.002/input MP per image (up to 5)", inline=False)
        embed.add_field(name="/nana",    value="~$0.04  — google/nano-banana", inline=False)
        embed.add_field(name="/pimg",    value="~$0.005 text-to-image (prunaai/p-image) | ~$0.01 with images (prunaai/p-image-edit)", inline=False)
        embed.add_field(name="/qwen",    value="~$0.025 text-to-image (qwen/qwen-image) | ~$0.03 with images (qwen/qwen-image-edit-plus)", inline=False)
        embed.add_field(name="/zimg",    value="~$0.02  — prunaai/z-image-turbo (1920×1088, ~2MP output)", inline=False)
        embed.add_field(name="/blip",    value="~$0.00022  — salesforce/blip", inline=False)
        embed.add_field(name="/caption", value="~$0.0017  — lucataco/moondream2", inline=False)
        embed.add_field(name="/seed\n/continue", value="~$0.075/run  — bytedance/seedance-1-pro-fast (5s @ 480p, $0.015/s)", inline=False)
        embed.add_field(name="/pvid\n/zpvid",    value="~$0.16/run  — prunaai/p-video (8s @ 720p, $0.02/s)", inline=False)
        embed.add_field(name="/ideo",    value="$0.03/image  — ideogram-ai/ideogram-v4-turbo (2560x1440)", inline=False)
        embed.add_field(name="/mmaudio", value="~$0.0053  — zsxkib/mmaudio", inline=False)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))

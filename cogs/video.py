import asyncio
import base64

import discord
import replicate
import requests
from discord.ext import commands
from io import BytesIO

from error_log import log_error


class Video(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def seed(self, ctx: commands.Context, *, text: str):
        """Generate a video using Seedance 1 Lite.

        Usage: /seed prompt (text-to-video)
        Usage: /seed prompt + 1 image (image-to-video, first frame)
        Usage: /seed prompt + 2 images (first + last frame)
        """
        status_msg = await ctx.reply("🎬 Generating video, this may take a few minutes...")
        try:
            model_input = {
                "prompt": text,
                "duration": 5,
                "resolution": "480p",
                "aspect_ratio": "16:9",
                "fps": 24,
            }
            image_attachments = [
                a
                for a in ctx.message.attachments
                if a.content_type and a.content_type.startswith("image/")
            ]
            if image_attachments:
                img_bytes = await image_attachments[0].read()
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                model_input["image"] = (
                    f"data:{image_attachments[0].content_type};base64,{b64}"
                )
            if len(image_attachments) >= 2:
                img_bytes = await image_attachments[1].read()
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                model_input["last_frame_image"] = (
                    f"data:{image_attachments[1].content_type};base64,{b64}"
                )
            prediction = await asyncio.to_thread(
                replicate.models.predictions.create,
                model="bytedance/seedance-1-lite",
                input=model_input,
            )
            print(f"[seed] Prediction created: {prediction.id}")
            elapsed = 0
            while prediction.status not in ("succeeded", "failed", "canceled"):
                await asyncio.sleep(5)
                elapsed += 5
                prediction = await asyncio.to_thread(
                    replicate.predictions.get, prediction.id
                )
                print(f"[seed] {elapsed}s - status: {prediction.status}")
                await status_msg.edit(
                    content=f"🎬 Generating video... ({elapsed}s, status: {prediction.status})"
                )
            if prediction.status == "failed":
                error_msg = prediction.error or "Unknown error"
                await status_msg.edit(content=f"❌ Generation failed: {error_msg}")
            elif prediction.output:
                await status_msg.edit(content="Downloading...")
                video_response = await asyncio.to_thread(
                    requests.get, prediction.output, timeout=120
                )
                video_data = BytesIO(video_response.content)
                if video_data.getbuffer().nbytes > 25 * 1024 * 1024:
                    await status_msg.edit(
                        content=f"❌ File too large for Discord. URL:\n{prediction.output}"
                    )
                    return
                video_data.seek(0)
                await status_msg.edit(content="Uploading...")
                await ctx.reply(file=discord.File(video_data, "video.mp4"))
                await status_msg.delete()
            else:
                await status_msg.edit(
                    content=f"❌ No output returned. Status: {prediction.status}"
                )
        except Exception as e:
            log_error("seed", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Video(bot))

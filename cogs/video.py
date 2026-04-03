import asyncio

import discord
import replicate
import requests
from discord.ext import commands
from io import BytesIO

from cogs.utils import get_attachments, attachment_to_data_uri, url_to_data_uri
from error_log import log_error


async def poll_prediction(prediction, label: str, status_msg, emoji: str):
    """Poll a Replicate prediction until it completes, updating the status message."""
    elapsed = 0
    while prediction.status not in ("succeeded", "failed", "canceled"):
        await asyncio.sleep(5)
        elapsed += 5
        try:
            prediction = await asyncio.wait_for(
                asyncio.to_thread(replicate.predictions.get, prediction.id),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            print(f"[{label}] {elapsed}s - poll hung, retrying...")
            continue
        print(f"[{label}] {elapsed}s - status: {prediction.status}")
        await status_msg.edit(
            content=f"{emoji} Generating... ({elapsed}s, status: {prediction.status})"
        )
    return prediction


class Video(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def seed(self, ctx: commands.Context, *, text: str):
        """Generate a video using Seedance 1 Pro Fast.

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
            attachments, embed_urls = await get_attachments(ctx, "image/")
            if attachments:
                model_input["image"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["image"] = url_to_data_uri(embed_urls[0])
            if len(attachments) >= 2:
                model_input["last_frame_image"] = await attachment_to_data_uri(attachments[1])
            prediction = await asyncio.to_thread(
                replicate.models.predictions.create,
                model="bytedance/seedance-1-pro-fast",
                input=model_input,
            )
            print(f"[seed] Prediction created: {prediction.id}")
            prediction = await poll_prediction(prediction, "seed", status_msg, "🎬")
            if prediction.status == "failed":
                await status_msg.edit(content=f"❌ Generation failed: {prediction.error or 'Unknown error'}")
            elif prediction.output:
                await status_msg.edit(content="Downloading...")
                video_response = await asyncio.to_thread(
                    requests.get, str(prediction.output), timeout=(10, 120)
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

    @commands.command()
    async def mmaudio(self, ctx: commands.Context, *, text: str = ""):
        """Generate audio using MMAudio.

        Usage: /mmaudio prompt (text-to-audio)
        Usage: /mmaudio prompt + video attachment (video-to-audio)
        """
        status_msg = await ctx.reply("🎵 Generating audio, this may take a moment...")
        try:
            model_input = {
                "prompt": text,
                "negative_prompt": "music",
                "duration": 8,
                "num_steps": 25,
                "cfg_strength": 4.5,
            }
            attachments, embed_urls = await get_attachments(ctx, "video/")
            if attachments:
                model_input["video"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["video"] = url_to_data_uri(embed_urls[0], default_type="video/mp4", timeout=60)
            prediction = await asyncio.to_thread(
                replicate.predictions.create,
                version="62871fb59889b2d7c13777f08deb3b36bdff88f7e1d53a50ad7694548a41b484",
                input=model_input,
            )
            print(f"[mmaudio] Prediction created: {prediction.id}")
            prediction = await poll_prediction(prediction, "mmaudio", status_msg, "🎵")
            if prediction.status == "failed":
                await status_msg.edit(content=f"❌ Generation failed: {prediction.error or 'Unknown error'}")
            elif prediction.output:
                await status_msg.edit(content="Downloading...")
                audio_response = await asyncio.to_thread(
                    requests.get, str(prediction.output), timeout=(10, 120)
                )
                audio_data = BytesIO(audio_response.content)
                if audio_data.getbuffer().nbytes > 25 * 1024 * 1024:
                    await status_msg.edit(
                        content=f"❌ File too large for Discord. URL:\n{prediction.output}"
                    )
                    return
                audio_data.seek(0)
                await status_msg.edit(content="Uploading...")
                filename = "video.mp4" if attachments else "audio.flac"
                await ctx.reply(file=discord.File(audio_data, filename))
                await status_msg.delete()
            else:
                await status_msg.edit(
                    content=f"❌ No output returned. Status: {prediction.status}"
                )
        except Exception as e:
            log_error("mmaudio", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Video(bot))

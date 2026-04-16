import asyncio
import base64
import os
import subprocess
import tempfile

import discord
import replicate
import requests
from discord.ext import commands
from io import BytesIO

from cogs.utils import (
    get_attachments,
    attachment_to_data_uri,
    url_to_data_uri,
    unwrap_output,
    poll_prediction,
)
from cogs.error_log import log_error


def extract_last_frame(video_bytes: bytes) -> bytes:
    """Extract the last frame of a video as JPEG bytes using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(video_bytes)
        video_path = vf.name
    frame_path = video_path + ".jpg"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-sseof",
                "-1",
                "-i",
                video_path,
                "-update",
                "1",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                frame_path,
                "-y",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        with open(frame_path, "rb") as f:
            return f.read()
    finally:
        for p in (video_path, frame_path):
            try:
                os.unlink(p)
            except OSError:
                pass


async def run_seedance(
    ctx: commands.Context, model_input: dict, status_msg, label: str = "seed"
):
    """Run a Seedance prediction with polling and reply with the video."""
    prediction = await asyncio.to_thread(
        replicate.models.predictions.create,
        model="bytedance/seedance-1-pro-fast",
        input=model_input,
    )
    print(f"[{label}] Prediction created: {prediction.id}")
    prediction = await poll_prediction(prediction, label, status_msg, "🎬")
    if prediction.status == "failed":
        await status_msg.edit(
            content=f"❌ Generation failed: {prediction.error or 'Unknown error'}"
        )
        return
    if not prediction.output:
        await status_msg.edit(
            content=f"❌ No output returned. Status: {prediction.status}"
        )
        return
    await status_msg.edit(content="Downloading...")
    url = unwrap_output(prediction.output)
    video_response = await asyncio.to_thread(requests.get, url, timeout=(10, 120))
    video_data = BytesIO(video_response.content)
    if video_data.getbuffer().nbytes > 25 * 1024 * 1024:
        await status_msg.edit(content=f"❌ File too large for Discord. URL:\n{url}")
        return
    video_data.seek(0)
    await status_msg.edit(content="Uploading...")
    await ctx.reply(file=discord.File(video_data, "video.mp4"))
    await status_msg.delete()


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
        status_msg = await ctx.reply(
            "🎬 Generating video, this may take a few minutes..."
        )
        try:
            model_input = {
                "prompt": text,
                "duration": 8,
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
                model_input["last_frame_image"] = await attachment_to_data_uri(
                    attachments[1]
                )
            await run_seedance(ctx, model_input, status_msg, "seed")
        except Exception as e:
            log_error("seed", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")

    @commands.command(name="continue")
    async def continue_(self, ctx: commands.Context, *, text: str = ""):
        """Continue a previous /seed video using its last frame as the first frame.

        Usage: reply to a bot-generated video with /continue [optional new prompt]
        If no prompt is supplied, reuses the original /seed prompt.
        """
        if not ctx.message.reference:
            await ctx.reply("❌ Reply to a /seed video with /continue.")
            return
        status_msg = await ctx.reply(
            "🎬 Continuing video, this may take a few minutes..."
        )
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            video_attachments = [
                a
                for a in ref_msg.attachments
                if a.content_type and a.content_type.startswith("video/")
            ]
            if not video_attachments:
                await status_msg.edit(content="❌ The replied-to message has no video.")
                return
            await status_msg.edit(content="🎬 Extracting last frame...")
            video_bytes = await video_attachments[0].read()
            frame_bytes = await asyncio.to_thread(extract_last_frame, video_bytes)
            b64 = base64.b64encode(frame_bytes).decode("utf-8")
            first_frame = f"data:image/jpeg;base64,{b64}"

            prompt = text.strip()
            if not prompt and ref_msg.reference:
                try:
                    original = await ctx.channel.fetch_message(
                        ref_msg.reference.message_id
                    )
                    content = original.content.strip()
                    for prefix in ("/seed ", "/continue "):
                        if content.startswith(prefix):
                            prompt = content[len(prefix) :].strip()
                            break
                except discord.NotFound:
                    pass
            if not prompt:
                await status_msg.edit(
                    content="❌ Couldn't find original prompt. Provide one with /continue <prompt>."
                )
                return

            model_input = {
                "prompt": prompt,
                "duration": 8,
                "resolution": "480p",
                "aspect_ratio": "16:9",
                "fps": 24,
                "image": first_frame,
            }
            await status_msg.edit(content=f"🎬 Continuing with prompt: {prompt[:100]}")
            await run_seedance(ctx, model_input, status_msg, "continue")
        except subprocess.CalledProcessError as e:
            log_error("continue", e, ctx, text)
            await status_msg.edit(
                content=f"❌ ffmpeg failed: {e.stderr.decode()[:500] if e.stderr else e}"
            )
        except Exception as e:
            log_error("continue", e, ctx, text)
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
                "negative_prompt": "distortion, low quality, silence",
                "duration": 8,
                "num_steps": 50,
                "cfg_strength": 7.0,
            }
            attachments, embed_urls = await get_attachments(ctx, "video/")
            if attachments:
                model_input["video"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["video"] = url_to_data_uri(
                    embed_urls[0], default_type="video/mp4", timeout=60
                )
            prediction = await asyncio.to_thread(
                replicate.predictions.create,
                version="62871fb59889b2d7c13777f08deb3b36bdff88f7e1d53a50ad7694548a41b484",
                input=model_input,
            )
            print(f"[mmaudio] Prediction created: {prediction.id}")
            prediction = await poll_prediction(prediction, "mmaudio", status_msg, "🎵")
            if prediction.status == "failed":
                await status_msg.edit(
                    content=f"❌ Generation failed: {prediction.error or 'Unknown error'}"
                )
            elif prediction.output:
                await status_msg.edit(content="Downloading...")
                audio_response = await asyncio.to_thread(
                    requests.get, unwrap_output(prediction.output), timeout=(10, 120)
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

import asyncio
import base64
import os
import subprocess
import sys
import discord
from discord.ext import commands
import replicate
import requests
from io import BytesIO
from config.settings import settings

# Bot setup
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.command()
async def flux(ctx: commands.Context, *, text: str):
    """Generate an image using Flux AI.

    Usage: /flux your image description here
    """
    try:
        async with ctx.typing():
            output = replicate.models.predictions.create(
                model="prunaai/flux-fast",
                input={
                    "seed": -1,
                    "prompt": text,
                    "guidance": 8,
                    "image_size": 1024,
                    "speed_mode": "Lightly Juiced 🍊 (more consistent)",
                    "aspect_ratio": "1:1",
                    "output_format": "jpg",
                    "output_quality": 80,
                    "num_inference_steps": 28,
                },
                wait=True,
            )
            if output.status == "failed":
                error_msg = output.error or "Unknown error"
                await ctx.reply(f"❌ Generation failed: {error_msg}")
            elif output.output:
                image_response = requests.get(output.output, timeout=30)
                image_data = BytesIO(image_response.content)
                image_data.seek(0)
                await ctx.reply(file=discord.File(image_data, "generated_image.jpg"))
            else:
                await ctx.reply(f"❌ No output returned. Status: {output.status}")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def nana(ctx: commands.Context, *, text: str):
    """Generate an image using Google Nano Banana (Gemini Flash).

    Usage: /nana your image description here
    Attach images to use as reference input.
    """
    try:
        async with ctx.typing():
            model_input = {
                "prompt": text,
                "aspect_ratio": "16:9",
                "output_format": "jpg",
            }
            image_attachments = [
                a
                for a in ctx.message.attachments
                if a.content_type and a.content_type.startswith("image/")
            ]
            if image_attachments:
                data_uris = []
                for a in image_attachments:
                    img_bytes = await a.read()
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    data_uris.append(f"data:{a.content_type};base64,{b64}")
                model_input["image_input"] = data_uris
            output = replicate.models.predictions.create(
                model="google/nano-banana",
                input=model_input,
                wait=True,
            )
            if output.status == "failed":
                error_msg = output.error or "Unknown error"
                await ctx.reply(f"❌ Generation failed: {error_msg}")
            elif output.output:
                image_response = requests.get(output.output, timeout=30)
                image_data = BytesIO(image_response.content)
                image_data.seek(0)
                await ctx.reply(file=discord.File(image_data, "generated_image.jpg"))
            else:
                await ctx.reply(f"❌ No output returned. Status: {output.status}")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def zimg(ctx: commands.Context, *, text: str):
    """Generate an image using Z-Image Turbo.

    Usage: /zimg your image description here
    """
    try:
        async with ctx.typing():
            output = replicate.models.predictions.create(
                model="prunaai/z-image-turbo",
                input={
                    "prompt": text,
                    "width": 1920,
                    "height": 1088,
                    "guidance_scale": 0,
                    "num_inference_steps": 8,
                    "output_format": "jpg",
                    "output_quality": 80,
                },
                wait=True,
            )
            if output.status == "failed":
                error_msg = output.error or "Unknown error"
                await ctx.reply(f"❌ Generation failed: {error_msg}")
            elif output.output:
                image_response = requests.get(output.output, timeout=30)
                image_data = BytesIO(image_response.content)
                image_data.seek(0)
                await ctx.reply(file=discord.File(image_data, "generated_image.jpg"))
            else:
                await ctx.reply(f"❌ No output returned. Status: {output.status}")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def blip(ctx: commands.Context, *, text: str = ""):
    """Caption an image or ask a question about it using BLIP.

    Usage: /blip (attach an image for a caption)
    Usage: /blip what color is the car? (attach an image for VQA)
    """
    try:
        image_attachments = [
            a
            for a in ctx.message.attachments
            if a.content_type and a.content_type.startswith("image/")
        ]
        if not image_attachments:
            await ctx.reply("❌ Please attach an image.")
            return
        async with ctx.typing():
            img_bytes = await image_attachments[0].read()
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            data_uri = f"data:{image_attachments[0].content_type};base64,{b64}"
            model_input = {"image": data_uri}
            if text:
                model_input["task"] = "visual_question_answering"
                model_input["question"] = text
            else:
                model_input["task"] = "image_captioning"
            output = await asyncio.to_thread(
                replicate.run,
                "salesforce/blip:2e1dddc8621f72155f24cf2e0adbde548458d3cab9f00c0139eea840d0ac4746",
                input=model_input,
            )
            result = output if isinstance(output, str) else "".join(output)
            if result:
                await ctx.reply(result[:2000])
            else:
                await ctx.reply("❌ No output returned.")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def qwen(ctx: commands.Context, *, text: str = "Describe this content."):
    """Ask a question about an image or video using Qwen3-VL.

    Usage: /qwen (attach an image or video)
    Usage: /qwen what is happening here? (attach an image or video)
    """
    try:
        supported = [
            a
            for a in ctx.message.attachments
            if a.content_type
            and (
                a.content_type.startswith("image/")
                or a.content_type.startswith("video/")
            )
        ]
        if not supported:
            await ctx.reply("❌ Please attach an image or video.")
            return
        async with ctx.typing():
            attachment = supported[0]
            file_bytes = await attachment.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            data_uri = f"data:{attachment.content_type};base64,{b64}"
            output = await asyncio.to_thread(
                replicate.run,
                "lucataco/qwen3-vl-8b-instruct:39e893666996acf464cff75688ad49ac95ef54e9f1c688fbc677330acc478e11",
                input={
                    "media": data_uri,
                    "prompt": f"You are a video generation prompt writer. Analyze this image and write a detailed, vivid prompt that could be used to generate a video based on it. Describe the scene, subjects, actions, lighting, camera angle, mood, colors, and environment in explicit detail. Output ONLY the prompt text, nothing else. {text}",
                    "max_new_tokens": 256,
                },
            )
            result = output if isinstance(output, str) else "".join(output)
            if result:
                await ctx.reply(result)
            else:
                await ctx.reply("❌ No output returned.")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def caption(ctx: commands.Context, *, text: str = "Describe this image"):
    """Caption an image using Moondream2.

    Usage: /caption (attach an image)
    Usage: /caption what color is the car? (attach an image)
    """
    try:
        image_attachments = [
            a
            for a in ctx.message.attachments
            if a.content_type and a.content_type.startswith("image/")
        ]
        if not image_attachments:
            await ctx.reply("❌ Please attach an image to caption.")
            return
        async with ctx.typing():
            img_bytes = await image_attachments[0].read()
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            data_uri = f"data:{image_attachments[0].content_type};base64,{b64}"
            output = await asyncio.to_thread(
                replicate.run,
                "lucataco/moondream2:72ccb656353c348c1385df54b237eeb7bfa874bf11486cf0b9473e691b662d31",
                input={
                    "image": data_uri,
                    "prompt": text,
                },
            )
            result = "".join(output)
            if result:
                await ctx.reply(result[:2000])
            else:
                await ctx.reply("❌ No output returned.")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def seed(ctx: commands.Context, *, text: str):
    """Generate a video using Seedance 1 Lite.

    Usage: /seed your video description here
    Attach an image to use as the first frame.
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
        prediction = await asyncio.to_thread(
            replicate.models.predictions.create,
            model="bytedance/seedance-1-lite",
            input=model_input,
        )
        while prediction.status not in ("succeeded", "failed", "canceled"):
            await asyncio.sleep(5)
            await asyncio.to_thread(prediction.reload)
        if prediction.status == "failed":
            error_msg = prediction.error or "Unknown error"
            await status_msg.edit(content=f"❌ Generation failed: {error_msg}")
        elif prediction.output:
            await status_msg.edit(content=prediction.output)
        else:
            await status_msg.edit(
                content=f"❌ No output returned. Status: {prediction.status}"
            )
    except Exception as e:
        print(f"[seed] Error: {e}")
        try:
            await status_msg.edit(content=f"❌ An error occurred: {e}")
        except Exception:
            pass


@bot.command()
async def seed2(ctx: commands.Context, *, text: str):
    """Generate a video using Seedance 1 Lite.

    Usage: /seed2 prompt (text-to-video)
    Usage: /seed2 prompt + 1 image (image-to-video, first frame)
    Usage: /seed2 prompt + 2 images (first + last frame)
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
        print(f"[seed2] Prediction created: {prediction.id}")
        elapsed = 0
        while prediction.status not in ("succeeded", "failed", "canceled"):
            await asyncio.sleep(5)
            elapsed += 5
            prediction = await asyncio.to_thread(
                replicate.predictions.get, prediction.id
            )
            print(f"[seed2] {elapsed}s - status: {prediction.status}")
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
        await status_msg.edit(content=f"❌ An error occurred: {e}")


@bot.command()
async def help_bot(ctx):
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
        value="Generate a 5s video using Seedance 1 Lite (480p)\n• Attach an image for image-to-video\n• Example: `/seed a dog running on the beach`",
        inline=False,
    )

    embed.add_field(
        name="/seed2 <text>",
        value="Generate a 5s video with audio using Seedance 1.5 Pro (720p)\n• Attach an image for image-to-video\n• Example: `/seed2 a waterfall in a forest with birds chirping`",
        inline=False,
    )

    embed.add_field(name="/help_bot", value="Show this help message", inline=False)

    await ctx.reply(embed=embed)


@bot.command()
async def update(ctx: commands.Context):
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

    await bot.close()
    os.execv(sys.executable, [sys.executable] + sys.argv)


@bot.event
async def on_ready():
    print(f"{bot.user} has logged in!")


# Run the bot
settings.validate()
bot.run(settings.discord_token)

import asyncio
import base64
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
async def seed(ctx: commands.Context, *, text: str):
    """Generate a video using Seedance 1 Lite.

    Usage: /seed your video description here
    Attach an image to use as the first frame.
    """
    try:
        async with ctx.typing():
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
            prediction = replicate.models.predictions.create(
                model="bytedance/seedance-1-lite",
                input=model_input,
            )
            while prediction.status not in ("succeeded", "failed", "canceled"):
                await asyncio.sleep(5)
                await asyncio.to_thread(prediction.reload)
            if prediction.status == "failed":
                error_msg = prediction.error or "Unknown error"
                await ctx.reply(f"❌ Generation failed: {error_msg}")
            elif prediction.output:
                video_response = await asyncio.to_thread(
                    requests.get, prediction.output, timeout=120
                )
                video_data = BytesIO(video_response.content)
                video_data.seek(0)
                await ctx.reply(file=discord.File(video_data, "generated_video.mp4"))
            else:
                await ctx.reply(f"❌ No output returned. Status: {prediction.status}")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


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
        name="/seed <text>",
        value="Generate a 5s video using Seedance 1 Lite (480p)\n• Attach an image for image-to-video\n• Example: `/seed a dog running on the beach`",
        inline=False,
    )

    embed.add_field(name="/help_bot", value="Show this help message", inline=False)

    await ctx.reply(embed=embed)


@bot.event
async def on_ready():
    print(f"{bot.user} has logged in!")
    print("Bot is ready to caption images!")


# Run the bot
settings.validate()
bot.run(settings.discord_token)

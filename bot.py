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
            output_url = output.output
            if output_url:
                image_response = requests.get(output_url, timeout=30)
                image_data = BytesIO(image_response.content)
                image_data.seek(0)
                await ctx.reply(file=discord.File(image_data, "generated_image.jpg"))
            else:
                await ctx.reply("❌ No image was generated. Please try again.")
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
            image_urls = [
                a.url
                for a in ctx.message.attachments
                if a.content_type and a.content_type.startswith("image/")
            ]
            if image_urls:
                model_input["image_input"] = image_urls
            output = replicate.models.predictions.create(
                model="google/nano-banana",
                input=model_input,
                wait=True,
            )
            output_url = output.output
            if output_url:
                image_response = requests.get(output_url, timeout=30)
                image_data = BytesIO(image_response.content)
                image_data.seek(0)
                await ctx.reply(file=discord.File(image_data, "generated_image.jpg"))
            else:
                await ctx.reply("❌ No image was generated. Please try again.")
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
                    "height": 1080,
                    "guidance_scale": 0,
                    "num_inference_steps": 8,
                    "output_format": "jpg",
                    "output_quality": 80,
                },
                wait=True,
            )
            output_url = output.output
            if output_url:
                image_response = requests.get(output_url, timeout=30)
                image_data = BytesIO(image_response.content)
                image_data.seek(0)
                await ctx.reply(file=discord.File(image_data, "generated_image.jpg"))
            else:
                await ctx.reply("❌ No image was generated. Please try again.")
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

    embed.add_field(name="/help_bot", value="Show this help message", inline=False)

    await ctx.reply(embed=embed)


@bot.event
async def on_ready():
    print(f"{bot.user} has logged in!")
    print("Bot is ready to caption images!")


# Run the bot
settings.validate()
bot.run(settings.discord_token)

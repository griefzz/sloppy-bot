import discord
from discord.ext import commands
import requests
from io import BytesIO
from pathlib import Path

from services.better_flux import generate_better_flux_images


# Bot setup
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="/", intents=intents)

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
except ImportError:
    print("python-dotenv not installed. Using system environment variables.")

from config.settings import settings


@bot.command()
async def flux(ctx: commands.Context, *, text: str):
    """Generate an image using Flux AI.

    Usage: /flux your image description here
    """
    try:
        async with ctx.typing():
            # API request
            api_url = f"https://fast-flux-demo.replicate.workers.dev/api/generate-image?text={text}"
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                # Load image from response
                image_data = BytesIO(response.content)
                image_data.seek(0)
                # Send image as a reply
                await ctx.reply(file=discord.File(image_data, "generated_image.webp"))
            else:
                await ctx.reply(
                    f"❌ Failed to generate image (Status: {response.status_code}). Please try again later."
                )
    except requests.exceptions.Timeout:
        await ctx.reply("❌ Image generation timed out. Please try again.")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def dlux(ctx: commands.Context, *, text: str):
    """Generate an image using Flux AI.

    Usage: /dflux your image description here
    """
    try:
        async with ctx.typing():
            images_data = generate_better_flux_images(text, aspect_ratio="16:9")

            if images_data and len(images_data) > 0:
                # Create Discord File objects for all images
                files = []
                for i, image_data in enumerate(images_data):
                    image_io = BytesIO(image_data)
                    image_io.seek(0)
                    files.append(discord.File(image_io, f"generated_image_{i + 1}.jpg"))

                # Send all images as a reply
                await ctx.reply(files=files)
            else:
                await ctx.reply("❌ Failed to generate images. Please try again later.")
    except Exception as e:
        await ctx.reply(f"❌ An error occurred: {e}")


@bot.command()
async def help_bot(ctx):
    """Show help information for the bot commands."""
    embed = discord.Embed(title="🤖 Bot Commands Help", color=0x0099FF)

    embed.add_field(
        name="/flux <text>",
        value="Generate an image using AI\n• Example: `/flux a cat wearing sunglasses`",
        inline=False,
    )

    embed.add_field(
        name="/dlux <text>",
        value="Generate multiple images using Flux AI\n• Example: `/dflux a serene mountain landscape`",
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

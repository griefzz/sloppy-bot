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
            # API request to Replicate
            api_url = (
                "https://api.replicate.com/v1/models/prunaai/flux-fast/predictions"
            )
            headers = {
                "Authorization": f"Bearer {settings.replicate_api_token}",
                "Content-Type": "application/json",
                "Prefer": "wait",
            }
            payload = {
                "input": {
                    "seed": -1,
                    "prompt": text,
                    "guidance": 3.5,
                    "image_size": 1024,
                    "speed_mode": "Extra Juiced 🔥 (more speed)",
                    "aspect_ratio": "1:1",
                    "output_format": "jpg",
                    "output_quality": 80,
                    "num_inference_steps": 28,
                }
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            if response.status_code in (200, 201):
                result = response.json()
                output_url = result.get("output")
                if output_url:
                    # Download the generated image
                    image_response = requests.get(output_url, timeout=30)
                    if image_response.status_code == 200:
                        image_data = BytesIO(image_response.content)
                        image_data.seek(0)
                        await ctx.reply(
                            file=discord.File(image_data, "generated_image.jpg")
                        )
                    else:
                        await ctx.reply("❌ Failed to download generated image.")
                else:
                    await ctx.reply("❌ No image was generated. Please try again.")
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

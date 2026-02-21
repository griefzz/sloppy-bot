import base64

import discord
import replicate
import requests
from discord.ext import commands
from io import BytesIO

from error_log import log_error


class Images(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def flux(self, ctx: commands.Context, *, text: str):
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
            log_error("flux", e, ctx, text)
            await ctx.reply(f"❌ An error occurred: {e}")

    @commands.command()
    async def nana(self, ctx: commands.Context, *, text: str):
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
            log_error("nana", e, ctx, text)
            await ctx.reply(f"❌ An error occurred: {e}")

    @commands.command()
    async def zimg(self, ctx: commands.Context, *, text: str):
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
            log_error("zimg", e, ctx, text)
            await ctx.reply(f"❌ An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Images(bot))

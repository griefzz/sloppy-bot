import asyncio

import replicate
from discord.ext import commands

from cogs.utils import get_attachments, to_data_uris, reply_with_file, run_image_model
from cogs.error_log import log_error


class Images(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def flux(self, ctx: commands.Context, *, text: str):
        """Generate an image using Flux AI.

        Usage: /flux your image description here
        """
        await run_image_model(ctx, "prunaai/flux-fast", {
            "seed": -1,
            "prompt": text,
            "guidance": 8,
            "image_size": 1024,
            "speed_mode": "Lightly Juiced 🍊 (more consistent)",
            "aspect_ratio": "1:1",
            "output_format": "jpg",
            "output_quality": 80,
            "num_inference_steps": 28,
        }, "generated_image.jpg", "flux")

    @commands.command()
    async def flux2(self, ctx: commands.Context, *, text: str):
        """Generate an image using FLUX.2 Klein 9B.

        Usage: /flux2 your image description here
        Attach 1-5 images for image-to-image, or reply to a message with images.
        """
        model_input = {
            "prompt": text,
            "aspect_ratio": "16:9",
            "output_format": "jpg",
            "output_quality": 95,
            "output_megapixels": "1",
            "disable_safety_checker": True,
        }
        attachments, embed_urls = await get_attachments(ctx, "image/")
        if attachments or embed_urls:
            model_input["images"] = await to_data_uris(attachments, embed_urls, limit=5)
            model_input["aspect_ratio"] = "match_input_image"
        await run_image_model(ctx, "black-forest-labs/flux-2-klein-9b", model_input, "generated_image.jpg", "flux2")

    @commands.command()
    async def nana(self, ctx: commands.Context, *, text: str):
        """Generate an image using Google Nano Banana (Gemini Flash).

        Usage: /nana your image description here
        Attach images to use as reference input, or reply to a message with images.
        """
        model_input = {
            "prompt": text,
            "aspect_ratio": "16:9",
            "output_format": "jpg",
        }
        attachments, embed_urls = await get_attachments(ctx, "image/")
        if attachments or embed_urls:
            model_input["image_input"] = await to_data_uris(attachments, embed_urls)
        await run_image_model(ctx, "google/nano-banana", model_input, "generated_image.jpg", "nana")

    @commands.command()
    async def pimg(self, ctx: commands.Context, *, text: str):
        """Generate or edit images using P-Image.

        Usage: /pimg your prompt here (text-to-image)
        Attach 1-5 images or reply to a message with an image to edit instead.
        """
        attachments, embed_urls = await get_attachments(ctx, "image/")
        if attachments or embed_urls:
            data_uris = await to_data_uris(attachments, embed_urls, limit=5)
            await run_image_model(ctx, "prunaai/p-image-edit", {
                "prompt": text,
                "images": data_uris,
                "aspect_ratio": "16:9",
                "disable_safety_checker": True,
            }, "generated_image.jpg", "pimg")
        else:
            await run_image_model(ctx, "prunaai/p-image", {
                "prompt": text,
                "aspect_ratio": "custom",
                "width": 1440,
                "height": 810,
                "disable_safety_checker": True,
            }, "generated_image.jpg", "pimg")

    @commands.command()
    async def qwen(self, ctx: commands.Context, *, text: str):
        """Generate or edit images using Qwen Image.

        Usage: /qwen your prompt here (text-to-image)
        Attach 1-3 images or reply to a message with images to edit instead.
        """
        attachments, embed_urls = await get_attachments(ctx, "image/")
        if attachments or embed_urls:
            try:
                async with ctx.typing():
                    data_uris = await to_data_uris(attachments, embed_urls, limit=3)
                    output = await asyncio.to_thread(
                        replicate.run,
                        "qwen/qwen-image-edit-plus",
                        input={
                            "image": data_uris,
                            "prompt": text,
                            "output_format": "jpg",
                            "aspect_ratio": "match_input_image",
                            "disable_safety_checker": True,
                        },
                    )
                    urls = output if isinstance(output, list) else [output]
                    if urls:
                        await reply_with_file(ctx, str(urls[0]), "edited_image.jpg")
                    else:
                        await ctx.reply("No output returned.")
            except Exception as e:
                log_error("qwen", e, ctx, text)
                await ctx.reply(f"An error occurred: {e}")
        else:
            await run_image_model(ctx, "qwen/qwen-image", {
                "prompt": text,
                "aspect_ratio": "16:9",
                "output_format": "jpg",
                "disable_safety_checker": True,
            }, "generated_image.jpg", "qwen")

    @commands.command()
    async def grok(self, ctx: commands.Context, *, text: str):
        """Generate or edit images using xAI Grok Imagine.

        Usage: /grok your image description here (text-to-image)
        Attach 1-3 images or reply to a message with images to edit instead.
        """
        attachments, embed_urls = await get_attachments(ctx, "image/")
        if attachments or embed_urls:
            data_uris = await to_data_uris(attachments, embed_urls, limit=3)
            await run_image_model(ctx, "xai/grok-imagine-image", {
                "prompt": text,
                "image": data_uris[0] if len(data_uris) == 1 else data_uris,
                "aspect_ratio": "match_input_image",
                "resolution": "2k",
            }, "generated_image.jpg", "grok")
        else:
            await run_image_model(ctx, "xai/grok-imagine-image", {
                "prompt": text,
                "aspect_ratio": "16:9",
                "resolution": "2k",
            }, "generated_image.jpg", "grok")

    @commands.command()
    async def ideo(self, ctx: commands.Context, *, text: str):
        """Generate an image using Ideogram v4 Turbo.

        Usage: /ideo your image description here
        """
        await run_image_model(ctx, "ideogram-ai/ideogram-v4-turbo", {
            "prompt": text,
            "resolution": "2560x1440",
            "enable_copyright_detection": False,
        }, "generated_image.jpg", "ideo")

    @commands.command()
    async def zimg(self, ctx: commands.Context, *, text: str):
        """Generate an image using Z-Image Turbo.

        Usage: /zimg your image description here
        """
        await run_image_model(ctx, "prunaai/z-image-turbo", {
            "prompt": text,
            "width": 1920,
            "height": 1088,
            "guidance_scale": 0,
            "num_inference_steps": 8,
            "output_format": "jpg",
            "output_quality": 80,
        }, "generated_image.jpg", "zimg")


async def setup(bot: commands.Bot):
    await bot.add_cog(Images(bot))

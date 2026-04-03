import asyncio
import base64
from io import BytesIO

import discord
import replicate
import requests
from discord.ext import commands

from error_log import log_error


class Vision(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def blip(self, ctx: commands.Context, *, text: str = ""):
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
            log_error("blip", e, ctx, text)
            await ctx.reply(f"❌ An error occurred: {e}")

    @commands.command()
    async def qwen(self, ctx: commands.Context, *, text: str):
        """Edit images using Qwen Image Edit Plus.

        Usage: /qwen your editing instructions here
        Attach 1-3 images to edit, or reply to a message with images.
        """
        try:
            image_attachments = [
                a
                for a in ctx.message.attachments
                if a.content_type and a.content_type.startswith("image/")
            ]
            embed_image_urls = []
            if not image_attachments and ctx.message.reference:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                image_attachments = [
                    a
                    for a in ref.attachments
                    if a.content_type and a.content_type.startswith("image/")
                ]
                if not image_attachments:
                    embed_image_urls = [
                        e.image.url or e.thumbnail.url
                        for e in ref.embeds
                        if e.image or e.thumbnail
                    ]
            if not image_attachments and not embed_image_urls:
                await ctx.reply("❌ Attach at least one image to edit, or reply to a message with an image.")
                return
            async with ctx.typing():
                data_uris = []
                if embed_image_urls:
                    for url in embed_image_urls[:3]:
                        img_response = requests.get(url, timeout=30)
                        b64 = base64.b64encode(img_response.content).decode("utf-8")
                        ct = img_response.headers.get("Content-Type", "image/jpeg")
                        data_uris.append(f"data:{ct};base64,{b64}")
                for a in image_attachments[:3]:
                    img_bytes = await a.read()
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    data_uris.append(f"data:{a.content_type};base64,{b64}")
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
                    img_response = requests.get(str(urls[0]), timeout=30)
                    img_data = BytesIO(img_response.content)
                    img_data.seek(0)
                    await ctx.reply(file=discord.File(img_data, "edited_image.jpg"))
                else:
                    await ctx.reply("❌ No output returned.")
        except Exception as e:
            log_error("qwen", e, ctx, text)
            await ctx.reply(f"❌ An error occurred: {e}")

    @commands.command()
    async def caption(self, ctx: commands.Context, *, text: str = "Describe this image"):
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
            log_error("caption", e, ctx, text)
            await ctx.reply(f"❌ An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Vision(bot))

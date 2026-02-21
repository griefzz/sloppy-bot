import asyncio
import base64

import replicate
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
    async def qwen(self, ctx: commands.Context, *, text: str = "Describe this content."):
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

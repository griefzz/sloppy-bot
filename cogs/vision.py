import asyncio

import replicate
from discord.ext import commands

from cogs.utils import get_attachments, attachment_to_data_uri, url_to_data_uri
from cogs.error_log import log_error


class Vision(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def blip(self, ctx: commands.Context, *, text: str = ""):
        """Caption an image or ask a question about it using BLIP.

        Usage: /blip (attach an image for a caption)
        Usage: /blip what color is the car? (attach an image for VQA)
        Reply to a message with an image to use that.
        """
        try:
            attachments, embed_urls = await get_attachments(ctx, "image/")
            if not attachments and not embed_urls:
                await ctx.reply("❌ Please attach an image, or reply to a message with an image.")
                return
            async with ctx.typing():
                if attachments:
                    data_uri = await attachment_to_data_uri(attachments[0])
                else:
                    data_uri = url_to_data_uri(embed_urls[0])
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
    async def caption(self, ctx: commands.Context, *, text: str = "Describe this image"):
        """Caption an image using Moondream2.

        Usage: /caption (attach an image)
        Usage: /caption what color is the car? (attach an image)
        Reply to a message with an image to use that.
        """
        try:
            attachments, embed_urls = await get_attachments(ctx, "image/")
            if not attachments and not embed_urls:
                await ctx.reply("❌ Please attach an image to caption, or reply to a message with an image.")
                return
            async with ctx.typing():
                if attachments:
                    data_uri = await attachment_to_data_uri(attachments[0])
                else:
                    data_uri = url_to_data_uri(embed_urls[0])
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

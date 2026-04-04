import base64

import discord
import requests
from discord.ext import commands
from io import BytesIO


async def get_attachments(ctx: commands.Context, media_type: str = "image/") -> tuple[list, list]:
    """Get media attachments from the message or its reply, including embeds.

    Returns (attachments, embed_urls) where attachments are discord.Attachment
    objects and embed_urls are URL strings from embeds.
    """
    attachments = [
        a for a in ctx.message.attachments
        if a.content_type and a.content_type.startswith(media_type)
    ]
    embed_urls = []
    if not attachments and ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        attachments = [
            a for a in ref.attachments
            if a.content_type and a.content_type.startswith(media_type)
        ]
        if not attachments:
            if media_type.startswith("image/"):
                embed_urls = [
                    e.image.url or e.thumbnail.url
                    for e in ref.embeds
                    if e.image or e.thumbnail
                ]
            elif media_type.startswith("video/"):
                embed_urls = [
                    e.video.url
                    for e in ref.embeds
                    if e.video
                ]
    return attachments, embed_urls


async def attachment_to_data_uri(attachment: discord.Attachment) -> str:
    """Convert a discord attachment to a base64 data URI."""
    img_bytes = await attachment.read()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{attachment.content_type};base64,{b64}"


def url_to_data_uri(url: str, default_type: str = "image/jpeg", timeout: int = 30) -> str:
    """Download a URL and convert to a base64 data URI."""
    response = requests.get(url, timeout=timeout)
    b64 = base64.b64encode(response.content).decode("utf-8")
    ct = response.headers.get("Content-Type", default_type)
    return f"data:{ct};base64,{b64}"


async def to_data_uris(attachments: list, embed_urls: list, limit: int = 5, default_type: str = "image/jpeg") -> list[str]:
    """Convert attachments and/or embed URLs to data URIs."""
    data_uris = []
    if embed_urls:
        for url in embed_urls[:limit]:
            data_uris.append(url_to_data_uri(url, default_type))
    for a in attachments[:limit]:
        data_uris.append(await attachment_to_data_uri(a))
    return data_uris


def unwrap_output(output):
    """Unwrap a Replicate output that may be a list, FileOutput, or string into a URL string."""
    if isinstance(output, list):
        output = output[0]
    return str(output)


async def reply_with_file(ctx: commands.Context, url, filename: str, status_msg=None):
    """Download a URL and reply with it as a Discord file. Returns True on success."""
    url = unwrap_output(url)
    response = requests.get(url, timeout=30)
    data = BytesIO(response.content)
    if data.getbuffer().nbytes > 25 * 1024 * 1024:
        msg = f"File too large for Discord. URL:\n{url}"
        if status_msg:
            await status_msg.edit(content=msg)
        else:
            await ctx.reply(msg)
        return False
    data.seek(0)
    await ctx.reply(file=discord.File(data, filename))
    return True


async def run_image_model(ctx: commands.Context, model: str, model_input: dict, filename: str, cmd_name: str):
    """Run a Replicate image model with wait=True, handle the result, and reply."""
    import replicate
    try:
        async with ctx.typing():
            output = replicate.models.predictions.create(
                model=model,
                input=model_input,
                wait=True,
            )
            if output.status == "failed":
                await ctx.reply(f"❌ Generation failed: {output.error or 'Unknown error'}")
            elif output.output:
                await reply_with_file(ctx, output.output, filename)
            else:
                await ctx.reply(f"❌ No output returned. Status: {output.status}")
    except Exception as e:
        from error_log import log_error
        log_error(cmd_name, e, ctx, model_input.get("prompt", ""))
        await ctx.reply(f"❌ An error occurred: {e}")

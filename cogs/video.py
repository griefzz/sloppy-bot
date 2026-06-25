import asyncio
import base64
import glob
import os
import subprocess
import tempfile

import discord
import replicate
import requests
from discord.ext import commands
from io import BytesIO

from cogs.utils import (
    get_attachments,
    attachment_to_data_uri,
    url_to_data_uri,
    unwrap_output,
    poll_prediction,
)
from cogs.error_log import log_error


def extract_last_frame(video_bytes: bytes) -> bytes:
    """Extract the last frame of a video as JPEG bytes using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(video_bytes)
        video_path = vf.name
    frame_path = video_path + ".jpg"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-sseof",
                "-1",
                "-i",
                video_path,
                "-update",
                "1",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                frame_path,
                "-y",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        with open(frame_path, "rb") as f:
            return f.read()
    finally:
        for p in (video_path, frame_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def get_video_duration(path: str) -> float:
    """Return a video's duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=30,
    )
    return float(result.stdout.strip())


def has_audio(path: str) -> bool:
    """Return True if the file has at least one audio stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=30,
    )
    return bool(result.stdout.strip())


def concat_and_fit(prev_bytes: bytes, new_bytes: bytes, target_mb: int = 25) -> bytes:
    """Concatenate two clips into one continuous stream re-encoded to fit target_mb.

    Both inputs are normalized to 1280x720 @ 24fps before joining, so a 480p prior
    clip and a 720p new clip stitch cleanly. Audio is preserved: each segment keeps
    its own audio, and any segment lacking an audio track is backfilled with silence
    so the streams stay aligned. Two-pass libx264 targets a byte budget derived from
    the combined duration. Returns mp4 bytes.

    Raises ValueError if the combined stream is too long to fit at acceptable quality.
    """
    MIN_VIDEO_KBPS = 300
    AUDIO_KBPS = 128
    paths: list[str] = []
    out_path = None
    log_file = None
    try:
        for data in (prev_bytes, new_bytes):
            tf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tf.write(data)
            tf.close()
            paths.append(tf.name)
        prev_path, new_path = paths

        durs = [get_video_duration(prev_path), get_video_duration(new_path)]
        auds = [has_audio(prev_path), has_audio(new_path)]
        duration = sum(durs)
        # leave ~5% headroom under the hard limit for container overhead
        budget_bits = target_mb * 1024 * 1024 * 8 * 0.95
        video_kbps = int(budget_bits / duration / 1000) - AUDIO_KBPS
        if video_kbps < MIN_VIDEO_KBPS:
            raise ValueError(
                f"Stream is too long ({duration:.0f}s) to fit in {target_mb} MB. "
                f"Start a fresh clip with /pvid."
            )

        out_tf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out_path = out_tf.name
        out_tf.close()
        log_file = out_path + "-pass"

        norm = (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24"
        )
        afmt = "aformat=sample_rates=44100:channel_layouts=stereo"

        # Pass 1 only analyzes video, so it uses a video-only graph (no lavfi input).
        video_graph = (
            f"[0:v]{norm}[v0];[1:v]{norm}[v1];[v0][v1]concat=n=2:v=1:a=0[outv]"
        )
        pass1 = [
            "ffmpeg", "-y", "-i", prev_path, "-i", new_path,
            "-filter_complex", video_graph, "-map", "[outv]",
            "-c:v", "libx264", "-b:v", f"{video_kbps}k", "-pix_fmt", "yuv420p",
            "-pass", "1", "-passlogfile", log_file, "-an", "-f", "null", os.devnull,
        ]
        subprocess.run(pass1, check=True, capture_output=True, timeout=300)

        # Pass 2 carries audio. A silent anullsrc input (index 2) backfills any
        # segment without its own audio track, trimmed to that segment's duration.
        parts = [f"[0:v]{norm}[v0]", f"[1:v]{norm}[v1]"]
        for i in range(2):
            if auds[i]:
                parts.append(f"[{i}:a]{afmt}[a{i}]")
            else:
                parts.append(
                    f"[2:a]atrim=0:{durs[i]:.3f},asetpts=PTS-STARTPTS,{afmt}[a{i}]"
                )
        parts.append("[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]")
        full_graph = ";".join(parts)

        pass2 = [
            "ffmpeg", "-y", "-i", prev_path, "-i", new_path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex", full_graph, "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-b:v", f"{video_kbps}k", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k",
            "-pass", "2", "-passlogfile", log_file,
            "-movflags", "+faststart", out_path,
        ]
        subprocess.run(pass2, check=True, capture_output=True, timeout=300)

        with open(out_path, "rb") as f:
            return f.read()
    finally:
        cleanup = list(paths)
        if out_path:
            cleanup.append(out_path)
        if log_file:
            # ffmpeg writes "<passlogfile>-<stream_idx>.log" (+ ".mbtree"), so glob the prefix
            cleanup += glob.glob(f"{log_file}*.log") + glob.glob(f"{log_file}*.log.mbtree")
        for p in cleanup:
            try:
                os.unlink(p)
            except OSError:
                pass


async def predict_video_bytes(
    ctx: commands.Context, model: str, model_input: dict, status_msg, label: str
):
    """Run a Replicate video model with polling and return (video_bytes, url), or None on failure."""
    prediction = await asyncio.to_thread(
        replicate.models.predictions.create,
        model=model,
        input=model_input,
    )
    print(f"[{label}] Prediction created: {prediction.id}")
    prediction = await poll_prediction(prediction, label, status_msg, "🎬")
    if prediction.status == "failed":
        await status_msg.edit(
            content=f"❌ Generation failed: {prediction.error or 'Unknown error'}"
        )
        return None
    if not prediction.output:
        await status_msg.edit(
            content=f"❌ No output returned. Status: {prediction.status}"
        )
        return None
    await status_msg.edit(content="Downloading...")
    url = unwrap_output(prediction.output)
    video_response = await asyncio.to_thread(requests.get, url, timeout=(10, 120))
    return video_response.content, url


async def run_video_model(
    ctx: commands.Context, model: str, model_input: dict, status_msg, label: str
):
    """Run a Replicate video model with polling and reply with the video."""
    result = await predict_video_bytes(ctx, model, model_input, status_msg, label)
    if result is None:
        return
    content, url = result
    video_data = BytesIO(content)
    if video_data.getbuffer().nbytes > 25 * 1024 * 1024:
        await status_msg.edit(content=f"❌ File too large for Discord. URL:\n{url}")
        return
    video_data.seek(0)
    await status_msg.edit(content="Uploading...")
    await ctx.reply(file=discord.File(video_data, "video.mp4"))
    await status_msg.delete()


class Video(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def seed(self, ctx: commands.Context, *, text: str):
        """Generate a video using Seedance 1 Pro Fast.

        Usage: /seed prompt (text-to-video)
        Usage: /seed prompt + 1 image (image-to-video, first frame)
        Usage: /seed prompt + 2 images (first + last frame)
        """
        status_msg = await ctx.reply(
            "🎬 Generating video, this may take a few minutes..."
        )
        try:
            model_input = {
                "prompt": text,
                "duration": 5,
                "resolution": "480p",
                "aspect_ratio": "16:9",
                "fps": 24,
            }
            attachments, embed_urls = await get_attachments(ctx, "image/")
            if attachments:
                model_input["image"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["image"] = url_to_data_uri(embed_urls[0])
            if len(attachments) >= 2:
                model_input["last_frame_image"] = await attachment_to_data_uri(
                    attachments[1]
                )
            await run_video_model(
                ctx, "bytedance/seedance-1-pro-fast", model_input, status_msg, "seed"
            )
        except Exception as e:
            log_error("seed", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")

    @commands.command(name="continue")
    async def continue_(self, ctx: commands.Context, *, text: str = ""):
        """Continue a previous /pvid video and stitch it into one continuous stream.

        Generates a new 8s P-Video clip seeded from the replied-to video's last
        frame, then concatenates the previous video + new clip and re-encodes the
        result to fit Discord's upload limit before posting.

        Usage: reply to a bot-generated video with /continue [optional new prompt]
        If no prompt is supplied, reuses the original /pvid prompt.
        """
        if not ctx.message.reference:
            await ctx.reply("❌ Reply to a /pvid video with /continue.")
            return
        status_msg = await ctx.reply(
            "🎬 Continuing video, this may take a few minutes..."
        )
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            video_attachments = [
                a
                for a in ref_msg.attachments
                if a.content_type and a.content_type.startswith("video/")
            ]
            if not video_attachments:
                await status_msg.edit(content="❌ The replied-to message has no video.")
                return
            await status_msg.edit(content="🎬 Extracting last frame...")
            video_bytes = await video_attachments[0].read()
            frame_bytes = await asyncio.to_thread(extract_last_frame, video_bytes)
            b64 = base64.b64encode(frame_bytes).decode("utf-8")
            first_frame = f"data:image/jpeg;base64,{b64}"

            prompt = text.strip()
            if not prompt and ref_msg.reference:
                try:
                    original = await ctx.channel.fetch_message(
                        ref_msg.reference.message_id
                    )
                    content = original.content.strip()
                    for prefix in ("/pvid ", "/zpvid ", "/seed ", "/continue "):
                        if content.startswith(prefix):
                            prompt = content[len(prefix) :].strip()
                            break
                except discord.NotFound:
                    pass
            if not prompt:
                await status_msg.edit(
                    content="❌ Couldn't find original prompt. Provide one with /continue <prompt>."
                )
                return

            model_input = {
                "prompt": prompt,
                "duration": 8,
                "resolution": "720p",
                "aspect_ratio": "16:9",
                "fps": 24,
                "disable_safety_filter": True,
                "prompt_upsampling": True,
                "image": first_frame,
            }
            await status_msg.edit(content=f"🎬 Continuing with prompt: {prompt[:100]}")
            result = await predict_video_bytes(
                ctx, "prunaai/p-video", model_input, status_msg, "continue"
            )
            if result is None:
                return
            new_bytes, _ = result

            await status_msg.edit(content="🎬 Stitching clips into one stream...")
            try:
                combined = await asyncio.to_thread(concat_and_fit, video_bytes, new_bytes)
            except ValueError as e:
                await status_msg.edit(content=f"❌ {e}")
                return
            video_data = BytesIO(combined)
            if video_data.getbuffer().nbytes > 25 * 1024 * 1024:
                await status_msg.edit(content="❌ Combined stream too large for Discord.")
                return
            video_data.seek(0)
            await status_msg.edit(content="Uploading...")
            await ctx.reply(file=discord.File(video_data, "video.mp4"))
            await status_msg.delete()
        except subprocess.CalledProcessError as e:
            log_error("continue", e, ctx, text)
            await status_msg.edit(
                content=f"❌ ffmpeg failed: {e.stderr.decode()[:500] if e.stderr else e}"
            )
        except Exception as e:
            log_error("continue", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")

    @commands.command()
    async def pvid(self, ctx: commands.Context, *, text: str):
        """Generate a video using P-Video (prunaai/p-video).

        Usage: /pvid prompt (text-to-video)
        Usage: /pvid prompt + 1 image (image-to-video, first frame)
        Usage: /pvid prompt + 2 images (first + last frame)
        """
        status_msg = await ctx.reply(
            "🎬 Generating video, this may take a few minutes..."
        )
        try:
            model_input = {
                "prompt": text,
                "duration": 8,
                "resolution": "720p",
                "aspect_ratio": "16:9",
                "fps": 24,
                "disable_safety_filter": True,
                "prompt_upsampling": True,
            }
            attachments, embed_urls = await get_attachments(ctx, "image/")
            if attachments:
                model_input["image"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["image"] = url_to_data_uri(embed_urls[0])
            if len(attachments) >= 2:
                model_input["last_frame_image"] = await attachment_to_data_uri(attachments[1])
            await run_video_model(
                ctx, "prunaai/p-video", model_input, status_msg, "pvid"
            )
        except Exception as e:
            log_error("pvid", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")

    @commands.command()
    async def zpvid(self, ctx: commands.Context, *, text: str):
        """Generate a video using P-Video with prompt_upsampling disabled.

        Usage: /zpvid prompt (text-to-video, raw prompt, no auto-enhance)
        Usage: /zpvid prompt + 1 image (image-to-video, first frame)
        Usage: /zpvid prompt + 2 images (first + last frame)
        """
        status_msg = await ctx.reply(
            "🎬 Generating video, this may take a few minutes..."
        )
        try:
            model_input = {
                "prompt": text,
                "duration": 8,
                "resolution": "720p",
                "aspect_ratio": "16:9",
                "fps": 24,
                "prompt_upsampling": False,
                "disable_safety_filter": True,
            }
            attachments, embed_urls = await get_attachments(ctx, "image/")
            if attachments:
                model_input["image"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["image"] = url_to_data_uri(embed_urls[0])
            if len(attachments) >= 2:
                model_input["last_frame_image"] = await attachment_to_data_uri(attachments[1])
            await run_video_model(
                ctx, "prunaai/p-video", model_input, status_msg, "zpvid"
            )
        except Exception as e:
            log_error("zpvid", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")

    @commands.command()
    async def mmaudio(self, ctx: commands.Context, *, text: str = ""):
        """Generate audio using MMAudio.

        Usage: /mmaudio prompt (text-to-audio)
        Usage: /mmaudio prompt + video attachment (video-to-audio)
        """
        status_msg = await ctx.reply("🎵 Generating audio, this may take a moment...")
        try:
            model_input = {
                "prompt": text,
                "negative_prompt": "distortion, low quality, silence",
                "duration": 5,
                "num_steps": 50,
                "cfg_strength": 7.0,
            }
            attachments, embed_urls = await get_attachments(ctx, "video/")
            if attachments:
                model_input["video"] = await attachment_to_data_uri(attachments[0])
            elif embed_urls:
                model_input["video"] = url_to_data_uri(
                    embed_urls[0], default_type="video/mp4", timeout=60
                )
            prediction = await asyncio.to_thread(
                replicate.predictions.create,
                version="62871fb59889b2d7c13777f08deb3b36bdff88f7e1d53a50ad7694548a41b484",
                input=model_input,
            )
            print(f"[mmaudio] Prediction created: {prediction.id}")
            prediction = await poll_prediction(prediction, "mmaudio", status_msg, "🎵")
            if prediction.status == "failed":
                await status_msg.edit(
                    content=f"❌ Generation failed: {prediction.error or 'Unknown error'}"
                )
            elif prediction.output:
                await status_msg.edit(content="Downloading...")
                audio_response = await asyncio.to_thread(
                    requests.get, unwrap_output(prediction.output), timeout=(10, 120)
                )
                audio_data = BytesIO(audio_response.content)
                if audio_data.getbuffer().nbytes > 25 * 1024 * 1024:
                    await status_msg.edit(
                        content=f"❌ File too large for Discord. URL:\n{prediction.output}"
                    )
                    return
                audio_data.seek(0)
                await status_msg.edit(content="Uploading...")
                filename = "video.mp4" if attachments else "audio.flac"
                await ctx.reply(file=discord.File(audio_data, filename))
                await status_msg.delete()
            else:
                await status_msg.edit(
                    content=f"❌ No output returned. Status: {prediction.status}"
                )
        except Exception as e:
            log_error("mmaudio", e, ctx, text)
            await status_msg.edit(content=f"❌ An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Video(bot))

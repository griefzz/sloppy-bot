import collections
import datetime

from discord.ext import commands

# In-memory error log (last 50 errors, cleared on restart)
error_log: collections.deque = collections.deque(maxlen=50)


def log_error(command: str, error: Exception, ctx: commands.Context, user_input: str = ""):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    user = str(ctx.author) if ctx else "unknown"
    entry = f"[{timestamp}] /{command} | user: {user}"
    if user_input:
        entry += f" | input: {user_input[:80]}"
    entry += f"\n  {type(error).__name__}: {error}"
    error_log.append(entry)
    print(f"[error] {entry}")

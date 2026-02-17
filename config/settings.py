"""Configuration management for the bot."""

import os
from dotenv import load_dotenv
from pathlib import Path


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.discord_token = os.getenv("DISCORD_BOT_TOKEN")
        self.replicate_api_token = os.getenv("REPLICATE_API_TOKEN")
        self.command_prefix = os.getenv("COMMAND_PREFIX", "/")

    @property
    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return self.discord_token is not None

    def validate(self):
        """Validate required settings and raise error if missing."""
        if not self.discord_token:
            raise ValueError(
                "DISCORD_BOT_TOKEN environment variable is required. "
                "Please create a .env file or set the environment variable."
            )


# Load environment variables from .env file if it exists
try:
    env_path = Path(__file__).parent / ".." / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
except ImportError:
    print("python-dotenv not installed. Using system environment variables.")

# Global settings instance
settings = Settings()

"""Configuration management for the bot."""

import os


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


# Global settings instance
settings = Settings()

import hmac
import os
from fastapi.security import HTTPBasic
from pydantic import Field
from pydantic_settings import BaseSettings

"""
Shared services of settings and security
"""


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Listmonk configuration
    listmonk_url: str = Field(default="http://localhost:9000", description="Listmonk API URL")
    listmonk_admin_username: str = Field(
        default="admin", alias="LISTMONK_ADMIN_USER", description="Listmonk admin username"
    )
    listmonk_admin_password: str = Field(alias="LISTMONK_ADMIN_PASSWORD", description="Listmonk admin token/password")

    # RSS processing configuration
    rss_timeout: float = Field(default=30.0, alias="RSS_TIMEOUT", description="HTTP timeout for RSS feed requests")
    rss_user_agent: str = Field(
        default="RSS Monk/2.0 (Feed Aggregator; +https://github.com/wagov-dtt/rssmonk)",
        alias="RSS_USER_AGENT",
        description="User agent for RSS requests",
    )

    # Logging configuration
    log_level: str = Field(default="INFO", alias="LOG_LEVEL", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        alias="LOG_FORMAT",
        description="Log message format",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    def validate_required(self):
        """Validate required settings."""
        if not self.listmonk_admin_password:
            raise ValueError("LISTMONK_ADMIN_PASSWORD environment variable is required")

    def validate_admin_auth(self, username: str, password: str) -> bool:
        # Only used as a quick check against settings (env vars) before going to work against Listmonk.
        # No real check against Listmonk. Could be done by getting user 1
        # TODO - Ping against Listmonk. Access it's own user_role and check for Super Admin as it's a reserved role.
        return hmac.compare_digest(password, self.listmonk_admin_password) and username == self.listmonk_admin_username

    @classmethod
    def ensure_env_file(cls) -> bool:
        """Create .env file with defaults if it doesn't exist. Returns True if created."""
        env_path = ".env"
        if os.path.exists(env_path):
            return False

        # Generate .env content from field definitions
        env_content = "# RSS Monk Configuration\n"
        env_content += "# Auto-generated - modify as needed\n\n"

        # Required fields
        env_content += "# Required - get from your Listmonk instance\n"
        env_content += "LISTMONK_ADMIN_PASSWORD=your-token-here\n\n"

        # Optional fields with defaults
        env_content += "# Optional - uncomment and modify as needed\n"

        # Get field info from model
        for field_name, field_info in cls.model_fields.items():
            if field_name == "listmonk_password":  # Skip - handled above
                continue

            alias = getattr(field_info, "alias", None) or field_name.upper()
            default = field_info.default
            description = getattr(field_info, "description", "")

            if default is not None:
                # Format the default value appropriately
                if isinstance(default, str):
                    default_str = f'"{default}"' if " " in default else default
                else:
                    default_str = str(default).lower() if isinstance(default, bool) else str(default)

                env_content += f"# {alias}={default_str}"
                if description:
                    env_content += f"  # {description}"
                env_content += "\n"

        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            return True
        except OSError:
            return False


# Initialize settings and create .env if missing
if Settings.ensure_env_file():
    print("Created .env file with default settings. Please edit LISTMONK_ADMIN_PASSWORD before starting.")
settings = Settings()


def get_settings() -> Settings:
    return settings


# Central security point
security = HTTPBasic()

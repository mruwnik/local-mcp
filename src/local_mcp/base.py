from mcp_base import create_oauth_server
from mcp_base.config import ServerConfig

from local_mcp import settings


def check_user(username: str, password: str) -> int | None:
    print(username, password)
    print(settings.USERNAME, settings.PASSWORD)
    if username == settings.USERNAME and password == settings.PASSWORD:
        return 1
    return None


# Create server with defaults
mcp = create_oauth_server("local-mcp", check_user, config=ServerConfig(port=3000))

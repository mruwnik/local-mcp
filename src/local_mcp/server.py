from mcp_base import create_oauth_server
from mcp_base.config import ServerConfig


def check_user(username: str, password: str) -> int | None:
    with open("users.txt") as f:
        for i, line in enumerate(f.readlines()):
            if line == f"{username}:{password}":
                return i
    return None


# Create server with defaults
mcp = create_oauth_server("local-mcp", check_user, config=ServerConfig(port=8765))


# Add your tools
@mcp.tool()
def echo(message: str) -> str:
    """Echo back the input message."""
    return f"Echo: {message}"


# Run the server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")

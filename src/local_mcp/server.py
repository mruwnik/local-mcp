from local_mcp.base import mcp
import local_mcp.music

# Run the server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")

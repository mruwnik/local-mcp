import os
import dotenv

dotenv.load_dotenv()


ROMPR_API_USER = os.getenv("ROMPR_API_USER")
ROMPR_API_PASSWORD = os.getenv("ROMPR_API_PASSWORD")

USERNAME = os.getenv("LOCAL_MCP_USER")
PASSWORD = os.getenv("LOCAL_MCP_PASSWORD")

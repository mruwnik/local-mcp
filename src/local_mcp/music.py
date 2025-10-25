from local_mcp.base import mcp
from local_mcp.settings import ROMPR_API_USER, ROMPR_API_PASSWORD
import httpx
import base64
from bs4 import BeautifulSoup


BASE_URL = "https://media.ahiru.pl/music/api"
SONG_ATTRIBUTES = [
    "file",
    "folder",
    "Title",
    "Album",
    "Artist",
    "Track",
    "Date",
    "Genre",
    "Playcount",
    "Id",
    "Pos",
    "albumartist",
    "trackartist",
    "lastplayed",
    "metadata",
    "duration",
]


def _get_auth_headers() -> dict[str, str]:
    """Get authentication headers for RompЯ API."""
    auth_str = f"{ROMPR_API_USER}:{ROMPR_API_PASSWORD}"
    auth_bytes = auth_str.encode("ascii")
    auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
    return {
        "Authorization": f"Basic {auth_b64}",
        "Cookie": "player_backend=mpd",
    }


@mcp.tool()
async def mpd_player_command(commands: list[list[str]]) -> dict:
    """
    Execute MPD player commands. Commands should be a list of command arrays.

    Examples:
    - Play: [["play"]]
    - Pause: [["pause"]]
    - Stop: [["stop"]]
    - Next track: [["next"]]
    - Previous track: [["previous"]]
    - Clear playlist: [["clear"]]
    - Add track: [["add", "Artist/Album/track.mp3"]]
    - Set volume: [["volume", "75"]]
    - Set random: [["random", "1"]] (0=off, 1=on)
    - Set repeat: [["repeat", "1"]] (0=off, 1=on)
    - Multiple: [["clear"], ["add", "path.mp3"], ["play"]]

    Returns player status including current track info.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/player/",
            headers=_get_auth_headers(),
            json=commands,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def mpd_browse_directory(path: str = "") -> dict[str, list[dict[str, str]]]:
    """
    Browse MPD music directory. Returns files and subdirectories.

    Args:
        path: Directory path to browse (empty string for root)

    Returns dictionary with 'files' and 'directories' keys.
    """
    async with httpx.AsyncClient() as client:
        params = {"path": path} if path else {}
        response = await client.get(
            f"{BASE_URL}/dirbrowser/",
            headers=_get_auth_headers(),
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tracks = [
            {
                "file": track.get("name"),
                "title": track.select(".expand")[0].text,
                "duration": track.select(".tracktime")[0].text,
            }
            for track in soup.select(".clicktrack")
        ]
        folders = [
            {
                "folder": folder.select("input", type="hidden", name="dirpath")[0].get(
                    "value"
                ),
                "title": folder.select(".expand")[0].text,
            }
            for folder in soup.select(".clickalbum")
        ]
        return {"files": tracks, "directories": folders}


@mcp.tool()
async def mpd_get_playlist(fields: list[str] = SONG_ATTRIBUTES) -> list[dict]:
    """
    Get current MPD playlist/queue.

    Returns list of tracks in current queue.

    Args:
        fields: List of fields to return (default: all available fields)

    Returns list of tracks in current queue.
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/tracklist/",
                headers=_get_auth_headers(),
                timeout=60.0,
            )
            response.raise_for_status()
            return [
                {
                    attribute: value
                    for attribute, value in track.items()
                    if attribute in fields
                }
                for track in response.json()
            ]
    except Exception as e:
        print(e)
        return [{"error": str(e)}]


@mcp.tool()
async def mpd_play_tracks(
    tracks: list[str], clear_first: bool = True, start_playing: bool = True
) -> dict:
    """
    Add tracks to playlist and optionally start playback.

    Args:
        tracks: List of track paths (e.g., ["Artist/Album/01.mp3", "Artist/Album/02.mp3"])
        clear_first: Whether to clear playlist first (default: True)
        start_playing: Whether to start playing after adding (default: True)

    Returns player status.
    """
    commands = []

    if clear_first:
        commands.append(["clear"])

    for track in tracks:
        commands.append(["add", track])

    if start_playing:
        commands.append(["play"])

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/player/",
            headers=_get_auth_headers(),
            json=commands,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def mpd_get_status() -> dict:
    """
    Get current MPD player status.

    Returns info about current track, playback state, volume, etc.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/player/",
            headers=_get_auth_headers(),
            json=[["status"]],
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

from typing import TypedDict
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


class File(TypedDict):
    file: str
    title: str
    duration: str


class Folder(TypedDict):
    folder: str
    title: str


class Directory(TypedDict):
    files: list[File]
    directories: list[Folder]


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


async def get_files(client: httpx.AsyncClient, path: str = "") -> Directory:
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
        File(
            file=str(track.get("name") or ""),
            title=track.select(".expand")[0].text,
            duration=track.select(".tracktime")[0].text,
        )
        for track in soup.select(".clicktrack")
    ]
    folders = [
        Folder(
            folder=str(
                folder.select("input", type="hidden", name="dirpath")[0].get("value")
                or ""
            ),
            title=folder.select(".expand")[0].text,
        )
        for folder in soup.select(".clickalbum")
    ]
    return Directory(files=tracks, directories=folders)


@mcp.tool()
async def mpd_browse_directory(paths: list[str] = []) -> dict[str, Directory]:
    """
    Browse MPD music directory. Returns files and subdirectories.

    Args:
        paths: List of directory paths to browse (empty list for root)

    Returns a dict of {<path>: <Directory>}, where `Directory` is a dict with `files` and `directories` keys.
    """
    async with httpx.AsyncClient() as client:
        return {path: await get_files(client, path) for path in paths or [""]}


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

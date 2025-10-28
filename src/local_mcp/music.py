import base64
import random
import re
import time
from typing import TypedDict
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from local_mcp.base import mcp
from local_mcp.settings import CACHE_TIMEOUT, ROMPR_API_PASSWORD, ROMPR_API_USER

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


def select_text(element: Tag, selector: str) -> str:
    val = element.select(selector)
    if not val:
        return ""
    return val[0].text


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
            file=unquote(str(track.get("name") or "")),
            title=select_text(track, ".expand"),
            duration=select_text(track, ".tracktime"),
        )
        for track in soup.select(".clicktrack")
    ]
    folders = [
        Folder(
            folder=unquote(
                str(
                    folder.select("input", type="hidden", name="dirpath")[0].get(
                        "value"
                    )
                    or ""
                )
            ),
            title=select_text(folder, ".expand"),
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


cache = {}


def should_skip(path: str, skip: str | None) -> bool:
    return bool(skip and re.search(skip, path)) or "The Dresden Files" in path


async def get_all_files(
    client: httpx.AsyncClient, path: str = "", skip: str | None = None
) -> list[File]:
    key = (path, skip)
    if key in cache:
        res, ts = cache[key]
        if time.time() - ts < CACHE_TIMEOUT:
            return res

    res = []
    if not should_skip(path, skip):
        directory = await get_files(client, path)
        all_files = [file for file in directory["files"]]
        for directory in directory["directories"]:
            all_files += await get_all_files(client, directory["folder"], skip)
        res = [file for file in all_files if not should_skip(file["file"], skip)]

    cache[key] = (res, time.time())
    return res


@mcp.tool()
async def mdp_play_random_tracks(
    path: str = "",
    count: int = 10,
    clear_first: bool = True,
    start_playing: bool = True,
    skip: str | None = None,
) -> dict:
    """
    Play random tracks from a directory.

    This works recursively, by first getting all files from all subdirectories, then choosing `count` random files from the list.

    Args:
        path: Path to the directory to play tracks from
        count: Number of tracks to play
        clear_first: Whether to clear playlist first (default: True)
        start_playing: Whether to start playing after adding (default: True)
        skip: a regular expression to skip files
            If provided, the file will be skipped if it matches the regular expression.

    Returns player status.
    """
    async with httpx.AsyncClient() as client:
        all_files = await get_all_files(client, path, skip)
        random_files = random.choices(all_files, k=min(count, len(all_files)))
        return await mpd_play_tracks(
            sorted([unquote(file["file"]) for file in random_files]),
            clear_first,
            start_playing,
        )


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

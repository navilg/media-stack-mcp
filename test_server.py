import argparse
import asyncio
import socket
import tempfile
import time
import traceback
import subprocess
import sys
from unittest.mock import patch
from requests import RequestException
from dotenv import load_dotenv
import os

from fastmcp import Client
from fastmcp.client.transports import SSETransport

import server


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
PASS_ICON = "✓"
FAIL_ICON = "✗"


def _run_test_case(test_func) -> tuple[bool, str | None, str | None]:
    """Run one test case and capture failures without stopping the full run."""
    try:
        test_func()
        return True, None, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", traceback.format_exc().strip()


def _parse_tsv(tsv_str: str) -> list[dict]:
    """Parse a TSV string into a list of dicts."""
    if not tsv_str or not tsv_str.strip():
        return []
    lines = tsv_str.strip().split("\n")
    headers = lines[0].split("\t")
    records = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        record = {}
        for i, header in enumerate(headers):
            record[header] = values[i] if i < len(values) else ""
        records.append(record)
    return records


def _set_env(overrides: dict[str, str | None]) -> dict[str, str | None]:
    """Temporarily set/unset env vars and return previous values for restore."""
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    """Restore env vars previously captured by _set_env."""
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value




# ---------------------------------------------------------------------------
# Toolset / tag parsing tests (no network required)
# ---------------------------------------------------------------------------


def test_valid_toolsets():
    """Valid toolset names pass validation."""
    assert server._parse_toolsets("") == ""
    assert server._parse_toolsets("floppy") == "floppy"
    assert server._parse_toolsets("trakt") == "trakt"
    assert server._parse_toolsets("radarr") == "radarr"
    assert server._parse_toolsets("sonarr") == "sonarr"
    assert server._parse_toolsets("trakt,radarr") == "trakt,radarr"
    assert server._parse_toolsets("trakt,sonarr") == "trakt,sonarr"
    assert server._parse_toolsets("radarr,trakt") == "radarr,trakt"


def test_parse_toolsets_handles_whitespace():
    """Whitespace around toolset names is tolerated."""
    assert server._parse_toolsets("  trakt  ") == "  trakt  "
    assert server._parse_toolsets(" trakt , radarr ") == " trakt , radarr "


def test_parse_toolsets_invalid():
    """Unknown toolset names raise ArgumentTypeError."""
    try:
        server._parse_toolsets("invalid_toolset")
        assert False, "Expected argparse.ArgumentTypeError for invalid toolset"
    except argparse.ArgumentTypeError as exc:
        assert "invalid toolset: 'invalid_toolset'" in str(exc)

    try:
        server._parse_toolsets("trakt,bogus")
        assert False, "Expected argparse.ArgumentTypeError for invalid toolset in list"
    except argparse.ArgumentTypeError as exc:
        assert "invalid toolset: 'bogus'" in str(exc)


def test_compute_tags_to_disable_default():
    """Default (empty string) results in only 'deprecated'."""
    tags = server._compute_tags_to_disable("")
    assert tags == {"deprecated"}


def test_compute_tags_to_disable_with_trakt():
    """Disabling 'trakt' adds it to the deprecated tag."""
    tags = server._compute_tags_to_disable("trakt")
    assert tags == {"deprecated", "trakt"}


def test_compute_tags_to_disable_with_radarr():
    """Disabling 'radarr' adds it to the deprecated tag."""
    tags = server._compute_tags_to_disable("radarr")
    assert tags == {"deprecated", "radarr"}


def test_compute_tags_to_disable_with_sonarr():
    """Disabling 'sonarr' adds it to the deprecated tag."""
    tags = server._compute_tags_to_disable("sonarr")
    assert tags == {"deprecated", "sonarr"}


def test_compute_tags_to_disable_both():
    """Disabling both toolsets includes all three tags."""
    tags = server._compute_tags_to_disable("trakt,radarr")
    assert tags == {"deprecated", "trakt", "radarr"}


def test_compute_tags_to_disable_handles_whitespace():
    """Whitespace in the CSV argument is stripped."""
    tags = server._compute_tags_to_disable("  trakt , radarr  ")
    assert tags == {"deprecated", "trakt", "radarr"}


def test_compute_tags_to_disable_returns_fresh_set():
    """Each call returns a new set, no aliasing."""
    tags1 = server._compute_tags_to_disable("trakt")
    tags2 = server._compute_tags_to_disable("radarr")
    assert tags1 != tags2


# ---------------------------------------------------------------------------
# CLI integration tests (subprocess)
# ---------------------------------------------------------------------------


def test_server_help_does_not_mention_disable_toolsets_flag():
    """The --help output should not reference the removed --disable-toolsets flag."""
    result = subprocess.run(
        [sys.executable, "server.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--disable-toolsets" not in result.stdout
    assert "sse" in result.stdout
    assert "default: streamable-http" in result.stdout


def test_server_sse_transport():
    """The CLI serves a real MCP session over SSE without backend credentials."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    async def check_session():
        async with Client(SSETransport(f"http://127.0.0.1:{port}/sse"), timeout=5) as client:
            assert await client.ping()
            tools = await client.list_tools()
            assert any(tool.name == "get_floppy_popular_movies" for tool in tools)

    env = os.environ.copy()
    env.pop("DISABLE_TOOLSETS", None)
    with tempfile.TemporaryFile(mode="w+") as logs:
        process = subprocess.Popen(
            [sys.executable, "server.py", "--transport", "sse", "--host", "127.0.0.1", "--port", str(port)],
            stdout=logs,
            stderr=logs,
            env=env,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None or time.monotonic() >= deadline:
                    logs.seek(0)
                    raise AssertionError(f"SSE server failed to start: {logs.read()}")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.05)
            asyncio.run(check_session())
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_server_with_invalid_disable_toolsets_env_fails():
    """Passing an invalid DISABLE_TOOLSETS value should exit with an error."""
    env = os.environ.copy()
    env["DISABLE_TOOLSETS"] = "bogus"
    result = subprocess.run(
        [sys.executable, "server.py"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert result.returncode != 0
    assert "invalid toolset" in result.stderr


# ---------------------------------------------------------------------------
# Existing integration tests (unchanged, below)
# ---------------------------------------------------------------------------


def test_check_trakt_profile_privacy():
    print(f"\nTesting Trakt profile privacy for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result = server.check_trakt_profile_privacy(test_username)
    assert isinstance(result, str)
    assert "visibility is public" in result
    print(f"User '{test_username}' has a public profile")


def test_get_trakt_public_watched_movies():
    print(f"\nTesting Trakt public watched movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_watched_movies(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} watched movies for user '{test_username}'")
    print("Sample movie:", records[0])


def test_get_trakt_public_watched_shows():
    print(f"\nTesting Trakt public watched shows for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_watched_shows(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} watched shows for user '{test_username}'")
    print("Sample show:", records[0])

def test_get_trakt_public_watched_shows_validation_errors():
    print("\nTesting Trakt public watched shows validation")

    previous = _set_env({"TRAKT_CLIENT_ID": None})
    try:
        result = server.get_trakt_public_watched_shows("test-user")
        assert result == "Error: TRAKT_CLIENT_ID is not set"
    finally:
        _restore_env(previous)

    previous = _set_env({"TRAKT_CLIENT_ID": "test-client-id"})
    try:
        result = server.get_trakt_public_watched_shows("   ")
        assert result == "Error: username must not be empty"
    finally:
        _restore_env(previous)

    previous = _set_env({"TRAKT_CLIENT_ID": "test-client-id"})
    try:
        result = server.get_trakt_public_watched_shows("test-user", days=0)
        assert result == "Error: days must be greater than 0"
    finally:
        _restore_env(previous)


def test_get_trakt_public_liked_movies():
    print(f"\nTesting Trakt public liked movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_liked_movies(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} liked movies for user '{test_username}'")
    print("Sample movie:", records[0])
    assert all(int(record["user_rating"]) >= 7 for record in records)


def test_get_trakt_public_liked_shows():
    print(f"\nTesting Trakt public liked shows for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_liked_shows(test_username)
    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"

    records = _parse_tsv(result_tsv)
    if not records:
        print(f"No liked shows found for user '{test_username}'")
        return

    print(f"Retrieved {len(records)} liked shows for user '{test_username}'")
    print("Sample show:", records[0])
    assert "liked_consideration" in records[0]


def test_get_trakt_public_disliked_movies():
    print(f"\nTesting Trakt public disliked movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_disliked_movies(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} disliked movies for user '{test_username}'")
    print("Sample movie:", records[0])
    assert all(int(record["user_rating"]) <= 5 for record in records)


def test_get_floppy_latest_high_rated_movies_validation_errors():
    assert server.get_floppy_latest_high_rated_movies(days=0) == "Error: days must be greater than 0"
    assert server.get_floppy_latest_high_rated_movies(threshold_rating=-1) == "Error: threshold_rating must be between 0 and 10"
    assert server.get_floppy_latest_high_rated_movies(threshold_rating=11) == "Error: threshold_rating must be between 0 and 10"
    assert server.get_floppy_latest_high_rated_movies(limit=0) == "Error: limit must be greater than 0"

    previous = _set_env({"FLOPPY_URL": None, "FLOPPY_API_KEY": None})
    try:
        assert server.get_floppy_latest_high_rated_movies() == "Error: FLOPPY_URL is not set"
        os.environ["FLOPPY_URL"] = "http://localhost:8000"
        assert server.get_floppy_latest_high_rated_movies() == "Error: FLOPPY_API_KEY is not set"
    finally:
        _restore_env(previous)


def test_get_floppy_popular_movies_validation_errors():
    assert server.get_floppy_popular_movies(limit=0) == "Error: limit must be between 1 and 200"
    assert server.get_floppy_popular_movies(limit=201) == "Error: limit must be between 1 and 200"

    previous = _set_env({"FLOPPY_URL": None, "FLOPPY_API_KEY": None})
    try:
        assert server.get_floppy_popular_movies() == "Error: FLOPPY_URL is not set"
        os.environ["FLOPPY_URL"] = "http://localhost:8000"
        assert server.get_floppy_popular_movies() == "Error: FLOPPY_API_KEY is not set"
    finally:
        _restore_env(previous)


def test_get_floppy_watched_movies_validation_errors():
    assert server.get_floppy_watched_movies(days=0) == "Error: days must be greater than 0"
    assert server.get_floppy_watched_movies(days=-1) == "Error: days must be greater than 0"
    assert server.get_floppy_watched_movies(limit=0) == "Error: limit must be between 1 and 200"
    assert server.get_floppy_watched_movies(limit=201) == "Error: limit must be between 1 and 200"

    previous = _set_env({"FLOPPY_URL": None, "FLOPPY_API_KEY": None})
    try:
        assert server.get_floppy_watched_movies() == "Error: FLOPPY_URL is not set"
        os.environ["FLOPPY_URL"] = "http://localhost:8000"
        assert server.get_floppy_watched_movies() == "Error: FLOPPY_API_KEY is not set"
    finally:
        _restore_env(previous)


def test_get_floppy_watched_tv_seasons_validation_errors():
    with patch("media_stack.floppy.requests.get") as get:
        for days in (0, -1):
            assert server.get_floppy_watched_tv_seasons(days=days) == "Error: days must be greater than 0"
        for limit in (0, -1, 201):
            assert server.get_floppy_watched_tv_seasons(limit=limit) == "Error: limit must be between 1 and 200"
        with patch.dict(os.environ, {"FLOPPY_URL": "", "FLOPPY_API_KEY": ""}):
            assert server.get_floppy_watched_tv_seasons() == "Error: FLOPPY_URL is not set"
            os.environ["FLOPPY_URL"] = "http://localhost:8000"
            assert server.get_floppy_watched_tv_seasons() == "Error: FLOPPY_API_KEY is not set"
        get.assert_not_called()


def test_get_floppy_watched_history():
    """Movie and season history share date, status, and TSV behavior."""
    from datetime import datetime, timezone

    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    entries = [
        {
            "status": 3,
            "played_at_local": "2026-10-29T20:00:00",
            "display_title": "Dark - Season 1",
            "score": 8,
            "genres": ["Drama", "Mystery"],
            "play_count": 2,
            "item": {"title": "Season 1", "year": 2017},
        },
        {"status": 2, "display_title": "In progress"},
        {
            "status": " Completed ",
            "title": "Dark - Season 2",
            "media": {"details": {"year": 2019, "genres": ["Drama"]}},
        },
        {"status": "watching"},
        {"item": {}},
        {"status": 3, "item": {"title": "Season 3", "genres": ["Mystery"]}},
    ]
    for tool, media_type in (
        (server.get_floppy_watched_movies, "movie"),
        (server.get_floppy_watched_tv_seasons, "season"),
    ):
        with (
            patch("media_stack.floppy.get_floppy_config", return_value=("http://floppy", "test")),
            patch("media_stack.floppy.requests.get") as get,
            patch("media_stack.floppy.datetime") as clock,
        ):
            clock.now.return_value = now
            get.return_value.json.return_value = {"results": entries}
            result = tool(days=7, limit=10)
            assert result == (
                "watched_at\ttitle\tyear\tuser_rating\tgenre\tplay_count\n"
                "2026-10-29T20:00:00\tDark - Season 1\t2017\t8\tDrama,Mystery\t2\n"
                "\tDark - Season 2\t2019\t\tDrama\t\n"
                "\tSeason 3\t\t\tMystery\t"
            )
            get.assert_called_once_with(
                "http://floppy/api/v1/history/",
                params={
                    "flat": "1", "media_type": media_type,
                    "start_date": "2026-10-23", "end_date": "2026-10-30",
                    "limit": 10, "offset": 0,
                },
                headers={"X-API-Key": "test"},
                timeout=20,
            )
            get.return_value.raise_for_status.assert_called_once_with()
            get.return_value.json.return_value = {"results": []}
            assert tool() == "Empty list"
            assert get.call_args.kwargs["params"]["limit"] == 200
            assert get.call_args.kwargs["params"]["start_date"] == "2026-09-30"
            get.return_value.json.return_value = {"results": [{"status": "watching"}]}
            assert tool(limit=1) == "Empty list"
            assert get.call_args.kwargs["params"]["limit"] == 1


def test_get_floppy_watched_history_errors():
    for tool, label in (
        (server.get_floppy_watched_movies, "movies"),
        (server.get_floppy_watched_tv_seasons, "TV seasons"),
    ):
        with (
            patch("media_stack.floppy.get_floppy_config", return_value=("http://floppy", "test")),
            patch("media_stack.floppy.requests.get") as get,
        ):
            get.side_effect = RequestException("Unavailable")
            assert tool() == f"Error: Failed to fetch watched {label} from Floppy: Unavailable"
            get.side_effect = None
            get.return_value.raise_for_status.side_effect = RequestException("Forbidden")
            assert tool() == f"Error: Failed to fetch watched {label} from Floppy: Forbidden"
            get.return_value.raise_for_status.side_effect = None
            for payload in ({}, {"results": None}, {"results": [None]}, {"results": [{"status": 3, "item": ["invalid"]}]}):
                get.return_value.json.return_value = payload
                assert tool() == "Error: Invalid response from Floppy"
            get.return_value.json.side_effect = ValueError("Invalid JSON")
            assert tool() == "Error: Invalid response from Floppy"


def test_get_floppy_watched_tv_seasons_tool_schema():
    async def check_schema():
        async with Client(server.mcp) as client:
            tools = await client.list_tools()
            tool = next(tool for tool in tools if tool.name == "get_floppy_watched_tv_seasons")
            assert "floppy" in tool.meta["fastmcp"]["tags"]
            assert tool.inputSchema["properties"]["days"] == {"default": 30, "type": "integer"}
            assert tool.inputSchema["properties"]["limit"] == {"default": 200, "type": "integer"}
            assert not tool.inputSchema.get("required")
            with (
                patch("media_stack.floppy.get_floppy_config", return_value=("http://floppy", "test")),
                patch("media_stack.floppy.requests.get") as get,
            ):
                get.return_value.json.return_value = {"results": []}
                result = await client.call_tool("get_floppy_watched_tv_seasons", {})
                assert not result.is_error
                assert result.content[0].text == "Empty list"
                assert get.call_args.kwargs["params"]["media_type"] == "season"

    asyncio.run(check_schema())


def test_get_floppy_latest_high_rated_movies():
    from datetime import datetime, timedelta, timezone
    from unittest import SkipTest

    load_dotenv("test.env")
    if not os.getenv("FLOPPY_URL") or not os.getenv("FLOPPY_API_KEY"):
        raise SkipTest("Set FLOPPY_URL and FLOPPY_API_KEY for the Floppy integration test")

    result_tsv = server.get_floppy_latest_high_rated_movies()
    assert not result_tsv.startswith("Error:"), result_tsv
    if result_tsv == "Empty list":
        return
    records = _parse_tsv(result_tsv)
    assert 0 < len(records) <= 50
    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=30)).date()
    completed_dates = []
    for record in records:
        assert float(record["user_rating"]) >= 7
        completed_date = datetime.fromisoformat(record["completed_date"].replace("Z", "+00:00"))
        assert start_date <= completed_date.date() <= now_utc.date()
        completed_dates.append(completed_date)
    assert completed_dates == sorted(completed_dates, reverse=True)


def test_get_trakt_latest_high_rated_movies():
    print(f"\nTesting Trakt latest high-rated movies")
    result_tsv = server.get_trakt_latest_high_rated_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} latest high-rated movies from Trakt")
    print("Sample movie:", records[0])
    assert all(float(record["average_rating"]) >= 7 for record in records)


def test_get_trakt_latest_high_rated_shows():
    print("\nTesting Trakt latest high-rated shows")

    result_tsv = server.get_trakt_latest_high_rated_shows(days=7, threshold_rating=7.5, limit=10)

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} latest high-rated shows from Trakt")
    print("Sample show:", records[0])
    assert all(float(record["average_rating"]) >= 7.5 for record in records)


def test_get_trakt_popular_movies():
    print(f"\nTesting Trakt popular movies")
    result_tsv = server.get_trakt_popular_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} popular movies from Trakt")
    print("Sample movie:", records[0])


def test_get_trakt_trending_movies():
    print("\nTesting Trakt trending movies")

    result_tsv = server.get_trakt_trending_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    assert len(records) <= 20
    print(f"Retrieved {len(records)} trending movies from Trakt")
    print("Sample movie:", records[0])


def test_get_trakt_trending_shows():
    print("\nTesting Trakt trending shows")

    result_tsv = server.get_trakt_trending_shows()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    assert len(records) <= 20
    print(f"Retrieved {len(records)} trending shows from Trakt")
    print("Sample show:", records[0])


def test_get_trakt_popular_shows():
    print("\nTesting Trakt popular shows")

    result_tsv = server.get_trakt_popular_shows(limit=10)

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} popular shows from Trakt")
    print("Sample show:", records[0])


def test_search_trakt_movie_by_title():
    print("\nTesting Trakt movie title search")

    result_tsv = server.search_trakt_movie_by_title("Avatar")
    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} movies matching 'Avatar' from Trakt")
    print("Sample movie:", records[0])


def test_search_trakt_show_by_title():
    print("\nTesting Trakt show title search")

    result_tsv = server.search_trakt_show_by_title("Dark")

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"

    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} shows matching 'Dark' from Trakt")
    print("Sample show:", records[0])
    
def test_get_radarr_movies_output_formats():
    """Short output is the default; full output preserves all metadata."""
    movies = [
        {
            "title": "Zulu",
            "year": 2020,
            "monitored": True,
            "status": "released",
            "hasFile": True,
            "movieFile": {
                "path": "/movies/Zulu.mkv",
                "size": 1572864,
                "quality": {"quality": {"name": "Bluray-1080p"}},
            },
            "genres": ["Drama", "Action"],
            "runtime": 120,
            "certification": "PG-13",
            "tmdbId": 123,
            "imdbId": "tt123",
        },
        {"title": "Alpha", "year": 2021, "monitored": False, "hasFile": False},
    ]
    short_output = (
        "title\tyear\tmonitored\thas_file\n"
        "Alpha\t2021\tFalse\tFalse\n"
        "Zulu\t2020\tTrue\tTrue"
    )
    full_output = (
        "title\tyear\tmonitored\tstatus\thas_file\tfile_path\tfile_size_mb\t"
        "quality\tgenres\truntime\tcertification\ttmdb_id\timdb_id\n"
        + "\t".join(["Alpha", "2021", "False", "", "False"] + [""] * 8)
        + "\n"
        + "\t".join([
            "Zulu", "2020", "True", "released", "True", "/movies/Zulu.mkv",
            "1.5", "Bluray-1080p", "Drama,Action", "120 min", "PG-13", "123", "tt123",
        ])
    )
    with (
        patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
        patch("media_stack.radarr.requests.get") as get,
    ):
        get.return_value.json.return_value = movies
        assert server.get_radarr_movies() == short_output
        assert server.get_radarr_movies(full_details=False) == short_output
        assert server.get_radarr_movies(full_details=True) == full_output
        get.assert_called_with(
            "http://radarr/api/v3/movie", headers={"X-Api-Key": "test"}, timeout=20
        )
        assert get.return_value.raise_for_status.call_count == 3


def test_get_radarr_movies_empty_formats():
    """An empty library retains the existing response in both formats."""
    with (
        patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
        patch("media_stack.radarr.requests.get") as get,
    ):
        get.return_value.json.return_value = []
        assert server.get_radarr_movies() == "Empty list"
        assert server.get_radarr_movies(full_details=True) == "Empty list"


def test_get_radarr_movies_tool_schema():
    """MCP clients can optionally request full details, title, and object filters."""
    async def check_schema():
        async with Client(server.mcp) as client:
            tools = await client.list_tools()
            tool = next(tool for tool in tools if tool.name == "get_radarr_movies")
            parameter = tool.inputSchema["properties"]["full_details"]
            assert parameter["type"] == "boolean"
            assert parameter["default"] is False
            assert "full_details" not in tool.inputSchema.get("required", [])
            title_parameter = tool.inputSchema["properties"]["title"]
            assert {"type": "string"} in title_parameter["anyOf"]
            assert title_parameter["default"] is None
            assert "title" not in tool.inputSchema.get("required", [])
            filter_parameter = tool.inputSchema["properties"]["filter"]
            assert any(item.get("type") == "object" for item in filter_parameter["anyOf"])
            assert {"type": "null"} in filter_parameter["anyOf"]
            assert filter_parameter["default"] is None
            assert "filter" not in tool.inputSchema.get("required", [])

    asyncio.run(check_schema())


def test_get_radarr_movies_title_filter():
    """Partial title matching works in both formats and preserves all versions."""
    movies = [
        {"title": "Dune", "year": 2021},
        {"title": "Dune: Part Two", "year": 2024},
        {"title": " DUNE ", "year": 1984},
        {"title": "The Dune Story", "year": 2025},
        {"title": "Arrival", "year": 2016},
        {"year": 2000},
        {"title": None},
    ]
    with (
        patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
        patch("media_stack.radarr.requests.get") as get,
    ):
        get.return_value.json.return_value = movies
        for full_details in (False, True):
            records = _parse_tsv(
                server.get_radarr_movies(full_details=full_details, title="  dUnE  ")
            )
            assert len(records) == 4
            assert {record["year"] for record in records} == {"1984", "2021", "2024", "2025"}
            assert all("dune" in record["title"].lower() for record in records)
            assert ("status" in records[0]) is full_details
            assert server.get_radarr_movies(
                full_details=full_details, title="Missing"
            ) == "Empty list"
        assert len(server.get_radarr_movies().split("\n")) - 1 == len(movies)
        assert server.get_radarr_movies(title=None) == server.get_radarr_movies()


def test_get_radarr_movies_title_validation():
    """Blank title filters fail explicitly without making backend requests."""
    with patch("media_stack.radarr.requests.get") as get:
        for title in ("", "   "):
            assert server.get_radarr_movies(title=title) == "Error: title must not be empty"
        get.assert_not_called()


def test_get_radarr_movies_filter():
    """Each optional field filters raw metadata in both output formats."""
    movies = [
        {"title": "Zulu", "monitored": True, "hasFile": True,
         "genres": ["Drama", "Romance"], "certification": "R"},
        {"title": "Alpha", "monitored": False, "hasFile": False,
         "genres": ["Romance"], "certification": "PG-13"},
        {"title": "Beta", "monitored": True, "hasFile": False,
         "genres": ["Drama"], "certification": "R"},
        {"title": "Gamma", "monitored": False, "hasFile": True,
         "genres": ["Romantic Comedy"], "certification": "PG"},
        {"title": "Missing"},
        {"title": "Null", "genres": None, "certification": None},
    ]
    cases = [
        (None, ["Alpha", "Beta", "Gamma", "Missing", "Null", "Zulu"]),
        ({}, ["Alpha", "Beta", "Gamma", "Missing", "Null", "Zulu"]),
        ({"monitored": True}, ["Beta", "Zulu"]),
        ({"monitored": False}, ["Alpha", "Gamma"]),
        ({"has_file": True}, ["Gamma", "Zulu"]),
        ({"has_file": False}, ["Alpha", "Beta"]),
        ({"genre": "  rOmAnCe  "}, ["Alpha", "Zulu"]),
        ({"genre": "roman"}, []),
        ({"certification": " r "}, ["Beta", "Zulu"]),
        ({"certification": "PG"}, ["Gamma"]),
        ({"monitored": False, "has_file": False}, ["Alpha"]),
        ({"monitored": True, "has_file": True, "genre": "romance",
          "certification": "R"}, ["Zulu"]),
        ({"genre": "romance", "certification": "PG"}, []),
    ]
    with (
        patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
        patch("media_stack.radarr.requests.get") as get,
    ):
        get.return_value.json.return_value = movies
        for full_details in (False, True):
            for movie_filter, expected in cases:
                records = _parse_tsv(server.get_radarr_movies(
                    full_details=full_details, filter=movie_filter,
                ))
                assert [record["title"] for record in records] == expected
                if records:
                    assert ("status" in records[0]) is full_details
            assert server.get_radarr_movies(
                full_details=full_details, title="alpha", filter={"monitored": True}
            ) == "Empty list"
            records = _parse_tsv(server.get_radarr_movies(
                full_details=full_details, title=" zUL ", filter={"genre": "romance"}
            ))
            assert [record["title"] for record in records] == ["Zulu"]


def test_get_radarr_movies_filter_validation():
    """Invalid filter shapes, keys, and values fail before accessing Radarr."""
    cases = [
        ([], "Error: filter must be a JSON object"),
        ('{"monitored": true}', "Error: filter must be a JSON object"),
        ({"year": 2020}, "Error: unsupported filter key: year"),
        ({"hasFile": True}, "Error: unsupported filter key: hasFile"),
        ({"monitored": True, "unknown": True}, "Error: unsupported filter key: unknown"),
    ]
    for key in ("monitored", "has_file"):
        for value in ("true", "false", 0, 1, None, [], {}):
            cases.append(({key: value}, f"Error: filter.{key} must be a boolean"))
    for key in ("genre", "certification"):
        for value in ("", "   ", True, 1, None, [], {}):
            cases.append(({key: value}, f"Error: filter.{key} must be a non-empty string"))
    with (
        patch("media_stack.radarr.get_radarr_config") as config,
        patch("media_stack.radarr.requests.get") as get,
    ):
        for movie_filter, expected in cases:
            assert server.get_radarr_movies(filter=movie_filter) == expected
        config.assert_not_called()
        get.assert_not_called()


def test_get_radarr_movies_filter_mcp():
    """JSON objects reach filtering and validation through the registered tool."""
    async def check_filter():
        async with Client(server.mcp) as client:
            result = await client.call_tool("get_radarr_movies", {
                "filter": {"monitored": True, "has_file": True,
                           "genre": "romance", "certification": "R"},
            })
            assert result.data == "title\tyear\tmonitored\thas_file\nZulu\t\tTrue\tTrue"
            for movie_filter, expected in [
                ({"unknown": True}, "Error: unsupported filter key: unknown"),
                ({"monitored": "true"}, "Error: filter.monitored must be a boolean"),
                ({"has_file": 1}, "Error: filter.has_file must be a boolean"),
            ]:
                result = await client.call_tool("get_radarr_movies", {"filter": movie_filter})
                assert result.data == expected

    with (
        patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
        patch("media_stack.radarr.requests.get") as get,
    ):
        get.return_value.json.return_value = [
            {"title": "Zulu", "monitored": True, "hasFile": True,
             "genres": ["Romance"], "certification": "R"},
            {"title": "Alpha", "monitored": False},
        ]
        asyncio.run(check_filter())
        assert get.call_count == 1


def test_delete_radarr_movie_excludes_import_lists():
    """Deleting a movie excludes it from import lists regardless of file removal."""
    for kwargs, delete_files in [({}, True), ({"delete_files": True}, True), ({"delete_files": False}, False)]:
        with (
            patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
            patch("media_stack.radarr.requests.get") as get,
            patch("media_stack.radarr.requests.delete") as delete,
        ):
            get.return_value.json.return_value = [{"id": 42, "title": "Dune"}]
            result = server.delete_radarr_movie("  Dune  ", **kwargs)
            assert result == f"Deleted Radarr movie 'Dune' (delete_files={delete_files})"
            get.assert_called_once_with(
                "http://radarr/api/v3/movie/lookup",
                params={"term": "Dune"},
                headers={"X-Api-Key": "test"},
                timeout=20,
            )
            delete.assert_called_once_with(
                "http://radarr/api/v3/movie/42",
                params={"deleteFiles": str(delete_files).lower(), "addImportExclusion": "true"},
                headers={"X-Api-Key": "test"},
                timeout=20,
            )
            delete.return_value.raise_for_status.assert_called_once_with()


def test_delete_radarr_movie_request_failure():
    """A failed deletion must not report success."""
    with (
        patch("media_stack.radarr.get_radarr_config", return_value=("http://radarr", "test")),
        patch("media_stack.radarr.requests.get") as get,
        patch("media_stack.radarr.requests.delete") as delete,
    ):
        get.return_value.json.return_value = [{"id": 42, "title": "Dune"}]
        delete.return_value.raise_for_status.side_effect = RequestException("Deletion failed")
        assert server.delete_radarr_movie("Dune") == (
            "Error: Failed to delete movie from Radarr: Deletion failed"
        )


def test_get_radarr_movies():
    print("\nTesting Radarr movies list")
    result_tsv = server.get_radarr_movies()
    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0, "Expected at least one movie in Radarr"
    print(f"Retrieved {len(records)} movies from Radarr")
    print("Sample movie:", records[0])
    assert list(records[0]) == ["title", "year", "monitored", "has_file"]


def test_get_radarr_quality_profiles():
    print("\nTesting Radarr quality profiles list")

    result_tsv = server.get_radarr_quality_profiles()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} quality profiles from Radarr")
    print("Sample quality profile:", records[0])
    assert "id" in records[0]
    assert "name" in records[0]


def test_get_radarr_root_folders():
    print("\nTesting Radarr root folders list")

    result_tsv = server.get_radarr_root_folders()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} root folders from Radarr")
    print("Sample root folder:", records[0])
    assert "id" in records[0]
    assert "path" in records[0]


def test_get_sonarr_validation_errors():
    print("\nTesting Sonarr validation")

    previous = _set_env({"SONARR_URL": None, "SONARR_API_KEY": None})
    try:
        result = server.get_sonarr_shows()
        assert result == "Error: SONARR_URL is not set"
    finally:
        _restore_env(previous)

    previous = _set_env({"SONARR_URL": "http://localhost:8989", "SONARR_API_KEY": None})
    try:
        result = server.get_sonarr_shows()
        assert result == "Error: SONARR_API_KEY is not set"
    finally:
        _restore_env(previous)

def test_get_sonarr_shows_output_formats():
    """Short output is the default; full output preserves all series metadata."""
    shows = [
        {
            "title": "Zulu", "year": 2020, "monitored": True, "status": "continuing",
            "path": "/tv/Zulu", "seasons": [{"seasonNumber": 1}, {"seasonNumber": 2}],
            "statistics": {
                "episodeFileCount": 5, "totalEpisodeCount": 10, "sizeOnDisk": 1610612736,
            },
            "genres": ["Drama", "Mystery"], "runtime": 45, "network": "Example",
            "certification": "TV-14", "originalLanguage": {"name": "English"},
            "tvdbId": 123, "imdbId": "tt123",
        },
        {"title": "Alpha", "year": 2021, "monitored": False},
    ]
    short_output = (
        "title\tyear\tmonitored\tepisode_file_count\n"
        "Alpha\t2021\tFalse\t\nZulu\t2020\tTrue\t5"
    )
    full_output = (
        "title\tyear\tmonitored\tstatus\tpath\tseason_count\tepisode_file_count\t"
        "total_episode_count\tsize_on_disk_gb\tgenres\truntime\tnetwork\t"
        "certification\tlanguage\ttvdb_id\timdb_id\n"
        + "\t".join(["Alpha", "2021", "False", "", "", "0"] + [""] * 10)
        + "\n"
        + "\t".join([
            "Zulu", "2020", "True", "continuing", "/tv/Zulu", "2", "5", "10",
            "1.5", "Drama,Mystery", "45 min", "Example", "TV-14", "English", "123", "tt123",
        ])
    )
    with (
        patch("media_stack.sonarr.get_sonarr_config", return_value=("http://sonarr", "test")),
        patch("media_stack.sonarr.requests.get") as get,
    ):
        get.return_value.json.return_value = shows
        assert server.get_sonarr_shows() == short_output
        assert server.get_sonarr_shows(full_details=False) == short_output
        assert server.get_sonarr_shows(full_details=True) == full_output
        get.assert_called_with(
            "http://sonarr/api/v3/series", headers={"X-Api-Key": "test"}, timeout=20
        )
        assert get.return_value.raise_for_status.call_count == 3


def test_get_sonarr_shows_title_filter():
    """Partial title filtering works in both formats, including missing titles."""
    shows = [
        {"title": "Dark", "year": 2017},
        {"title": "Dark Matter", "year": 2024},
        {"title": "The Dark Crystal", "year": 2019},
        {"title": "Arrival", "year": 2016},
        {"year": 2000},
        {"title": None},
    ]
    with (
        patch("media_stack.sonarr.get_sonarr_config", return_value=("http://sonarr", "test")),
        patch("media_stack.sonarr.requests.get") as get,
    ):
        get.return_value.json.return_value = shows
        for full_details in (False, True):
            records = _parse_tsv(
                server.get_sonarr_shows(full_details=full_details, title="  dArK  ")
            )
            assert [record["title"] for record in records] == [
                "Dark", "Dark Matter", "The Dark Crystal",
            ]
            assert ("status" in records[0]) is full_details
            assert server.get_sonarr_shows(
                full_details=full_details, title="Missing"
            ) == "Empty list"
        assert len(server.get_sonarr_shows().split("\n")) - 1 == len(shows)
        assert server.get_sonarr_shows(title=None) == server.get_sonarr_shows()
        get.return_value.json.return_value = []
        assert server.get_sonarr_shows() == "Empty list"
        assert server.get_sonarr_shows(full_details=True) == "Empty list"


def test_get_sonarr_shows_title_validation():
    """Blank title filters fail explicitly without making backend requests."""
    with patch("media_stack.sonarr.requests.get") as get:
        for title in ("", "   "):
            assert server.get_sonarr_shows(title=title) == "Error: title must not be empty"
        get.assert_not_called()


def test_get_sonarr_shows_tool_schema():
    """MCP clients can request full details, title, and an optional object filter."""
    async def check_schema():
        async with Client(server.mcp) as client:
            tools = await client.list_tools()
            tool = next(tool for tool in tools if tool.name == "get_sonarr_shows")
            parameter = tool.inputSchema["properties"]["full_details"]
            assert parameter["type"] == "boolean"
            assert parameter["default"] is False
            assert "full_details" not in tool.inputSchema.get("required", [])
            title_parameter = tool.inputSchema["properties"]["title"]
            assert {"type": "string"} in title_parameter["anyOf"]
            assert title_parameter["default"] is None
            assert "title" not in tool.inputSchema.get("required", [])
            filter_parameter = tool.inputSchema["properties"]["filter"]
            assert any(item.get("type") == "object" for item in filter_parameter["anyOf"])
            assert {"type": "null"} in filter_parameter["anyOf"]
            assert filter_parameter["default"] is None
            assert "filter" not in tool.inputSchema.get("required", [])

    asyncio.run(check_schema())


def test_get_sonarr_shows_filter():
    """Each field filters raw series metadata without changing either output format."""
    shows = [
        {"title": "Zulu", "monitored": True, "statistics": {"episodeFileCount": 5},
         "genres": ["Mystery", "Drama"], "certification": "TV-MA"},
        {"title": "Alpha", "monitored": False, "statistics": {"episodeFileCount": 0},
         "genres": ["Drama"], "certification": "TV-14"},
        {"title": "Beta", "monitored": True, "statistics": {"episodeFileCount": 0},
         "genres": ["Comedy"], "certification": "TV-MA"},
        {"title": "Gamma", "monitored": False, "statistics": {"episodeFileCount": 1},
         "genres": ["Dramatic Comedy"], "certification": "TV-G"},
        {"title": "Missing"},
        {"title": "Null", "statistics": {"episodeFileCount": None},
         "genres": None, "certification": None},
    ]
    cases = [
        (None, ["Alpha", "Beta", "Gamma", "Missing", "Null", "Zulu"]),
        ({}, ["Alpha", "Beta", "Gamma", "Missing", "Null", "Zulu"]),
        ({"monitored": True}, ["Beta", "Zulu"]),
        ({"monitored": False}, ["Alpha", "Gamma"]),
        ({"has_file": True}, ["Gamma", "Zulu"]),
        ({"has_file": False}, ["Alpha", "Beta", "Missing", "Null"]),
        ({"genre": "  dRaMa  "}, ["Alpha", "Zulu"]),
        ({"genre": "dram"}, []),
        ({"certification": " tv-ma "}, ["Beta", "Zulu"]),
        ({"certification": "TV"}, []),
        ({"monitored": False, "has_file": False}, ["Alpha"]),
        ({"monitored": True, "has_file": True, "genre": "drama",
          "certification": "TV-MA"}, ["Zulu"]),
        ({"genre": "drama", "certification": "TV-G"}, []),
    ]
    with (
        patch("media_stack.sonarr.get_sonarr_config", return_value=("http://sonarr", "test")),
        patch("media_stack.sonarr.requests.get") as get,
    ):
        get.return_value.json.return_value = shows
        for full_details in (False, True):
            for show_filter, expected in cases:
                records = _parse_tsv(server.get_sonarr_shows(
                    full_details=full_details, filter=show_filter,
                ))
                assert [record["title"] for record in records] == expected
                if records:
                    assert ("status" in records[0]) is full_details
                    assert "has_file" not in records[0]
                    assert "episode_file_count" in records[0]
            assert server.get_sonarr_shows(
                full_details=full_details, title="alpha", filter={"monitored": True}
            ) == "Empty list"
            records = _parse_tsv(server.get_sonarr_shows(
                full_details=full_details, title=" zUL ", filter={"genre": "drama"}
            ))
            assert [record["title"] for record in records] == ["Zulu"]
            get.return_value.json.return_value = []
            assert server.get_sonarr_shows(
                full_details=full_details, filter={"has_file": False}
            ) == "Empty list"
            get.return_value.json.return_value = shows


def test_get_sonarr_shows_filter_validation():
    """Invalid filter objects fail before accessing configuration or Sonarr."""
    cases = [
        ([], "Error: filter must be a JSON object"),
        ('{"monitored": true}', "Error: filter must be a JSON object"),
        ({"year": 2020}, "Error: unsupported filter key: year"),
        ({"episode_file_count": 1}, "Error: unsupported filter key: episode_file_count"),
        ({"monitored": True, "unknown": True}, "Error: unsupported filter key: unknown"),
    ]
    for key in ("monitored", "has_file"):
        for value in ("true", "false", 0, 1, None, [], {}):
            cases.append(({key: value}, f"Error: filter.{key} must be a boolean"))
    for key in ("genre", "certification"):
        for value in ("", "   ", True, 1, None, [], {}):
            cases.append(({key: value}, f"Error: filter.{key} must be a non-empty string"))
    with (
        patch("media_stack.sonarr.get_sonarr_config") as config,
        patch("media_stack.sonarr.requests.get") as get,
    ):
        for show_filter, expected in cases:
            assert server.get_sonarr_shows(filter=show_filter) == expected
        config.assert_not_called()
        get.assert_not_called()


def test_get_sonarr_shows_filter_mcp():
    """The registered tool accepts JSON object filters and rejects invalid fields."""
    async def check_filter():
        async with Client(server.mcp) as client:
            result = await client.call_tool("get_sonarr_shows", {
                "filter": {"monitored": True, "has_file": True,
                           "genre": "drama", "certification": "TV-MA"},
            })
            assert result.data == "title\tyear\tmonitored\tepisode_file_count\nZulu\t\tTrue\t5"
            for show_filter, expected in [
                ({"unknown": True}, "Error: unsupported filter key: unknown"),
                ({"monitored": "true"}, "Error: filter.monitored must be a boolean"),
                ({"has_file": 1}, "Error: filter.has_file must be a boolean"),
            ]:
                result = await client.call_tool("get_sonarr_shows", {"filter": show_filter})
                assert result.data == expected

    with (
        patch("media_stack.sonarr.get_sonarr_config", return_value=("http://sonarr", "test")),
        patch("media_stack.sonarr.requests.get") as get,
    ):
        get.return_value.json.return_value = [
            {"title": "Zulu", "monitored": True, "statistics": {"episodeFileCount": 5},
             "genres": ["Drama"], "certification": "TV-MA"},
            {"title": "Alpha", "monitored": False},
        ]
        asyncio.run(check_filter())
        assert get.call_count == 1


def test_get_sonarr_shows():
    print("\nTesting Sonarr shows list")
    result_tsv = server.get_sonarr_shows()
    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0, "Expected at least one show in Sonarr"
    print(f"Retrieved {len(records)} shows from Sonarr")
    print("Sample show:", records[0])
    assert list(records[0]) == ["title", "year", "monitored", "episode_file_count"]


def test_get_sonarr_quality_profiles():
    print("\nTesting Sonarr quality profiles list")

    result_tsv = server.get_sonarr_quality_profiles()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} quality profiles from Sonarr")
    print("Sample quality profile:", records[0])
    assert "id" in records[0]
    assert "name" in records[0]


def test_get_sonarr_root_folders():
    print("\nTesting Sonarr root folders list")

    result_tsv = server.get_sonarr_root_folders()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} root folders from Sonarr")
    print("Sample root folder:", records[0])
    assert "id" in records[0]
    assert "path" in records[0]


def test_add_sonarr_show_validation_errors():
    print("\nTesting Sonarr add show validation")

    previous = _set_env({"SONARR_URL": None, "SONARR_API_KEY": None})
    try:
        result = server.add_sonarr_show("Dark", "/tv", 1, 1)
        assert result == "Error: SONARR_URL is not set"
    finally:
        _restore_env(previous)

    previous = _set_env({"SONARR_URL": "http://localhost:8989", "SONARR_API_KEY": "test"})
    try:
        result = server.add_sonarr_show("   ", "/tv", 1, 1)
        assert result == "Error: show_query must not be empty"

        result = server.add_sonarr_show("Dark", "   ", 1, 1)
        assert result == "Error: root_folder_path must not be empty"

        result = server.add_sonarr_show("Dark", "/tv", 1, -1)
        assert result == "Error: season_number_to_monitor must be greater than or equal to 0"
    finally:
        _restore_env(previous)


def test_delete_sonarr_show_excludes_import_lists():
    """Deleting a show excludes it from import lists regardless of file removal."""
    for kwargs, delete_files in [({}, True), ({"delete_files": True}, True), ({"delete_files": False}, False)]:
        with (
            patch("media_stack.sonarr.get_sonarr_config", return_value=("http://sonarr", "test")),
            patch("media_stack.sonarr.requests.get") as get,
            patch("media_stack.sonarr.requests.delete") as delete,
        ):
            get.return_value.json.return_value = [{"id": 42, "title": "Dark"}]
            result = server.delete_sonarr_show("  Dark  ", **kwargs)
            assert result == f"Deleted Sonarr show 'Dark' (delete_files={delete_files})"
            get.assert_called_once_with(
                "http://sonarr/api/v3/series/lookup",
                params={"term": "Dark"},
                headers={"X-Api-Key": "test"},
                timeout=20,
            )
            delete.assert_called_once_with(
                "http://sonarr/api/v3/series/42",
                params={"deleteFiles": str(delete_files).lower(), "addImportListExclusion": "true"},
                headers={"X-Api-Key": "test"},
                timeout=20,
            )
            delete.return_value.raise_for_status.assert_called_once_with()


def test_delete_sonarr_show_request_failure():
    """A failed deletion must not report success."""
    with (
        patch("media_stack.sonarr.get_sonarr_config", return_value=("http://sonarr", "test")),
        patch("media_stack.sonarr.requests.get") as get,
        patch("media_stack.sonarr.requests.delete") as delete,
    ):
        get.return_value.json.return_value = [{"id": 42, "title": "Dark"}]
        delete.return_value.raise_for_status.side_effect = RequestException("Deletion failed")
        assert server.delete_sonarr_show("Dark") == (
            "Error: Failed to delete show from Sonarr: Deletion failed"
        )


def test_delete_sonarr_show_validation_errors():
    print("\nTesting Sonarr delete show validation")

    previous = _set_env({"SONARR_URL": None, "SONARR_API_KEY": None})
    try:
        result = server.delete_sonarr_show("Dark")
        assert result == "Error: SONARR_URL is not set"
    finally:
        _restore_env(previous)

    previous = _set_env({"SONARR_URL": "http://localhost:8989", "SONARR_API_KEY": "test"})
    try:
        result = server.delete_sonarr_show("   ")
        assert result == "Error: show_query must not be empty"
    finally:
        _restore_env(previous)


if __name__ == "__main__":
    load_dotenv("test.env")
    tests = [
        test_valid_toolsets,
        test_get_floppy_latest_high_rated_movies_validation_errors,
        test_get_floppy_popular_movies_validation_errors,
        test_get_floppy_watched_movies_validation_errors,
        test_get_floppy_watched_tv_seasons_validation_errors,
        test_get_floppy_watched_history,
        test_get_floppy_watched_history_errors,
        test_get_floppy_watched_tv_seasons_tool_schema,
        test_parse_toolsets_handles_whitespace,
        test_parse_toolsets_invalid,
        test_compute_tags_to_disable_default,
        test_compute_tags_to_disable_with_trakt,
        test_compute_tags_to_disable_with_radarr,
        test_compute_tags_to_disable_with_sonarr,
        test_compute_tags_to_disable_both,
        test_compute_tags_to_disable_handles_whitespace,
        test_compute_tags_to_disable_returns_fresh_set,
        test_check_trakt_profile_privacy,
        test_get_trakt_public_watched_movies,
        test_get_trakt_public_liked_movies,
        test_get_trakt_public_liked_shows,
        test_get_trakt_public_disliked_movies,
        test_get_trakt_latest_high_rated_movies,
        test_get_trakt_latest_high_rated_shows,
        test_get_trakt_popular_movies,
        test_get_trakt_trending_movies,
        test_get_trakt_trending_shows,
        test_get_trakt_popular_shows,
        test_search_trakt_movie_by_title,
        test_search_trakt_show_by_title,
        test_get_radarr_movies,
        test_get_radarr_movies_output_formats,
        test_get_radarr_movies_empty_formats,
        test_get_radarr_movies_tool_schema,
        test_get_radarr_movies_title_filter,
        test_get_radarr_movies_title_validation,
        test_get_radarr_movies_filter,
        test_get_radarr_movies_filter_validation,
        test_get_radarr_movies_filter_mcp,
        test_get_radarr_quality_profiles,
        test_get_radarr_root_folders,
        test_delete_radarr_movie_excludes_import_lists,
        test_delete_radarr_movie_request_failure,
        test_get_sonarr_validation_errors,
        test_get_sonarr_shows,
        test_get_sonarr_shows_output_formats,
        test_get_sonarr_shows_title_filter,
        test_get_sonarr_shows_title_validation,
        test_get_sonarr_shows_tool_schema,
        test_get_sonarr_shows_filter,
        test_get_sonarr_shows_filter_validation,
        test_get_sonarr_shows_filter_mcp,
        test_get_sonarr_quality_profiles,
        test_get_sonarr_root_folders,
        test_add_sonarr_show_validation_errors,
        test_delete_sonarr_show_validation_errors,
        test_delete_sonarr_show_excludes_import_lists,
        test_delete_sonarr_show_request_failure,
        test_get_trakt_public_watched_shows,
        test_get_trakt_public_watched_shows_validation_errors,
    ]

    if os.getenv("FLOPPY_URL") and os.getenv("FLOPPY_API_KEY"):
        tests.append(test_get_floppy_latest_high_rated_movies)

    passed = 0
    failed = 0

    print(f"{YELLOW}Running {len(tests)} test cases...{RESET}")
    for test_func in tests:
        ok, error, tb_text = _run_test_case(test_func)
        if ok:
            passed += 1
            print(f"{GREEN}{PASS_ICON} PASS{RESET} {test_func.__name__}")
        else:
            failed += 1
            print(f"{RED}{FAIL_ICON} FAIL{RESET} {test_func.__name__}")
            print(f"{RED}  -> {error}{RESET}")
            if tb_text:
                print(f"{RED}{tb_text}{RESET}")

    print("\n" + "=" * 60)
    print(f"Summary: passed={passed}, failed={failed}, total={len(tests)}")
    if failed == 0:
        print(f"{GREEN}All test cases passed.{RESET}")
    else:
        print(f"{RED}Some test cases failed. See logs above.{RESET}")

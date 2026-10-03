import argparse
import os

from fastmcp import FastMCP

from media_stack.config import (
    compute_tags_to_disable as _compute_tags_to_disable,
    get_radarr_config as _get_radarr_config,
    parse_toolsets as _parse_toolsets,
)
from media_stack.constants import VALID_TOOLSETS
from media_stack.floppy import (
    get_floppy_latest_high_rated_movies,
    get_floppy_popular_movies,
    get_floppy_watched_movies,
)
from media_stack.formatting import to_tsv as _to_tsv
from media_stack.radarr import (
    add_radarr_movie,
    delete_radarr_movie,
    get_radarr_current_downloads,
    get_radarr_movies,
    get_radarr_root_folders,
    get_radarr_quality_profiles,
)
from media_stack.sonarr import (
    add_sonarr_show,
    delete_sonarr_show,
    get_sonarr_current_downloads,
    get_sonarr_quality_profiles,
    get_sonarr_root_folders,
    get_sonarr_shows,
)
from media_stack.trakt import (
    check_trakt_profile_privacy,
    get_trakt_latest_high_rated_movies,
    get_trakt_latest_high_rated_shows,
    get_trakt_public_liked_shows,
    get_trakt_popular_movies,
    get_trakt_popular_shows,
    get_trakt_trending_movies,
    get_trakt_trending_shows,
    get_trakt_public_disliked_movies,
    get_trakt_public_liked_movies,
    get_trakt_public_watched_movies,
    get_trakt_public_watched_shows,
    search_trakt_movie_by_title,
    search_trakt_show_by_title,
)

mcp = FastMCP(name="Media Stack MCP")


def _register_tools() -> None:
    mcp.tool(tags={"floppy"})(get_floppy_popular_movies)
    mcp.tool(tags={"floppy"})(get_floppy_latest_high_rated_movies)
    mcp.tool(tags={"floppy"})(get_floppy_watched_movies)

    trakt_tools = [
        check_trakt_profile_privacy,
        get_trakt_public_watched_movies,
        get_trakt_public_watched_shows,
        get_trakt_public_liked_movies,
        get_trakt_public_liked_shows,
        get_trakt_public_disliked_movies,
        get_trakt_latest_high_rated_movies,
        get_trakt_latest_high_rated_shows,
        get_trakt_popular_movies,
        get_trakt_popular_shows,
        get_trakt_trending_movies,
        get_trakt_trending_shows,
        search_trakt_movie_by_title,
        search_trakt_show_by_title,
    ]
    radarr_tools = [
        get_radarr_movies,
        get_radarr_quality_profiles,
        get_radarr_root_folders,
        add_radarr_movie,
        delete_radarr_movie,
        get_radarr_current_downloads,
    ]
    sonarr_tools = [
        get_sonarr_shows,
        get_sonarr_quality_profiles,
        get_sonarr_root_folders,
        add_sonarr_show,
        delete_sonarr_show,
        get_sonarr_current_downloads,
    ]

    for tool in trakt_tools:
        mcp.tool(tags={"trakt"})(tool)

    for tool in radarr_tools:
        mcp.tool(tags={"radarr"})(tool)

    for tool in sonarr_tools:
        mcp.tool(tags={"sonarr"})(tool)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Media Stack MCP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument(
        "--transport",
        type=str,
        default="streamable-http",
        help="Transport protocol to use: streamable-http, http, or sse (default: streamable-http)",
    )
    args = parser.parse_args()

    disable_toolsets_env = os.getenv("DISABLE_TOOLSETS", "")
    _parse_toolsets(disable_toolsets_env)
    tags_to_disable = _compute_tags_to_disable(disable_toolsets_env)

    mcp.disable(tags=tags_to_disable)
    mcp.run(transport=args.transport, host=args.host, port=args.port)


_register_tools()


if __name__ == "__main__":
    main()
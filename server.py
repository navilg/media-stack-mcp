import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

from media_stack.auth import create_bearer_auth
from media_stack.config import (
    compute_tags_to_disable as _compute_tags_to_disable,
    parse_toolsets as _parse_toolsets,
    get_media_tracker as _get_media_tracker,
    get_discovery_source as _get_discovery_source,
)
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
)
from media_stack.media_tracker import (
    get_watched_movies,
    get_watched_tv_seasons,
    get_liked_movies,
    get_liked_tv_seasons,
    get_disliked_movies,
    get_disliked_tv_seasons,
)
from media_stack.media_discovery import (
    get_trending_movies,
    get_trending_shows,
    get_popular_movies,
    get_popular_shows,
    get_high_rated_movies,
    get_high_rated_shows,
    search_movie_by_title,
    search_tv_show_by_title,
    get_movie_details,
    get_tv_show_details,
)


def _create_mcp(use_auth: bool = True) -> FastMCP:
    """Create and configure FastMCP instance.

    Args:
        use_auth: Whether to enable bearer token authentication

    Returns:
        Configured FastMCP instance
    """
    auth_provider = None
    if use_auth:
        auth_provider = create_bearer_auth(env_var="MCP_AUTH_TOKEN")

    return FastMCP(name="Media Stack MCP", auth=auth_provider)


def _register_tools(mcp: FastMCP) -> None:
    """Register all tools with the FastMCP instance.

    Args:
        mcp: FastMCP instance to register tools with
    """

    # Always register media tracker tools
    media_tracker_tools = [
        get_watched_movies,
        get_watched_tv_seasons,
        get_liked_movies,
        get_liked_tv_seasons,
        get_disliked_movies,
        get_disliked_tv_seasons,
    ]
    for tool in media_tracker_tools:
        mcp.tool(tags={"media_tracker"})(tool)

    # Always register media discovery tools
    media_discovery_tools = [
        get_trending_movies,
        get_trending_shows,
        get_popular_movies,
        get_popular_shows,
        get_high_rated_movies,
        get_high_rated_shows,
        search_movie_by_title,
        search_tv_show_by_title,
        get_movie_details,
        get_tv_show_details,
    ]
    for tool in media_discovery_tools:
        mcp.tool(tags={"media_discovery"})(tool)

    # Register check_trakt_profile_privacy if using Trakt for either tracking or discovery
    if _get_media_tracker() == "trakt" or _get_discovery_source() == "trakt":
        mcp.tool()(check_trakt_profile_privacy)

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

    for tool in radarr_tools:
        mcp.tool(tags={"radarr"})(tool)

    for tool in sonarr_tools:
        mcp.tool(tags={"sonarr"})(tool)


def main() -> None:
    # Load environment variables from .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
    
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

    # Enable authentication only for streamable-http transport
    use_auth = args.transport == "streamable-http"
    mcp = _create_mcp(use_auth=use_auth)

    # Warn if streamable-http transport is used without authentication
    if args.transport == "streamable-http" and not os.getenv("MCP_AUTH_TOKEN"):
        print(
            "⚠️  WARNING: Running streamable-http transport without MCP_AUTH_TOKEN "
            "environment variable. This means the server is running without authentication. "
            "Set MCP_AUTH_TOKEN to enable bearer token authentication.",
            file=sys.stderr,
        )

    mcp.disable(tags=tags_to_disable)
    _register_tools(mcp)
    mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
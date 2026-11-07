"""Media tracker router tools that route to either Floppy or Trakt based on configuration."""

from media_stack.config import get_media_tracker
from media_stack.logging_util import log_tool_call

# Import floppy tools needed for routing
from media_stack.floppy import (
    get_floppy_watched_movies as _floppy_watched_movies,
    get_floppy_watched_tv_seasons as _floppy_watched_tv_seasons,
    get_floppy_liked_movies as _floppy_liked_movies,
    get_floppy_liked_tv_seasons as _floppy_liked_tv_seasons,
    get_floppy_disliked_movies as _floppy_disliked_movies,
    get_floppy_disliked_tv_seasons as _floppy_disliked_tv_seasons,
)

# Import trakt tools needed for routing
from media_stack.trakt import (
    get_trakt_public_watched_movies as _trakt_watched_movies,
    get_trakt_public_watched_shows as _trakt_watched_tv_seasons,
    get_trakt_public_liked_movies as _trakt_liked_movies,
    get_trakt_public_liked_shows as _trakt_liked_tv_seasons,
    get_trakt_public_disliked_movies as _trakt_disliked_movies,
)


@log_tool_call
def get_watched_movies(
    days: int = 30,
    limit: int = 200,
    username: str | None = None,
) -> str:
    """List watched movies as TSV. Routes to configured media tracker (TRACKED_MEDIA_SOURCE env var). Errors as strings."""
    tracker = get_media_tracker()
    if tracker == "floppy":
        return _floppy_watched_movies(days=days, limit=limit)
    else:  # trakt
        return _trakt_watched_movies(username=username, days=days)


@log_tool_call
def get_watched_tv_seasons(
    days: int = 30,
    limit: int = 200,
    username: str | None = None,
) -> str:
    """List watched TV seasons as TSV. Routes to configured media tracker (TRACKED_MEDIA_SOURCE env var). Errors as strings."""
    tracker = get_media_tracker()
    if tracker == "floppy":
        return _floppy_watched_tv_seasons(days=days, limit=limit)
    else:  # trakt
        return _trakt_watched_tv_seasons(username=username, days=days)


@log_tool_call
def get_liked_movies(
    threshold_user_rating: int = 7,
    days: int = 30,
    limit: int = 50,
    username: str | None = None,
) -> str:
    """List liked movies as TSV. Routes to configured media tracker (TRACKED_MEDIA_SOURCE env var). Errors as strings."""
    tracker = get_media_tracker()
    if tracker == "floppy":
        return _floppy_liked_movies(
            threshold_user_rating=threshold_user_rating,
            days=days,
            limit=limit,
        )
    else:  # trakt
        return _trakt_liked_movies(
            username=username,
            threshold_user_rating=threshold_user_rating,
            limit=limit,
        )


@log_tool_call
def get_liked_tv_seasons(
    threshold_user_rating: int = 8,
    days: int = 30,
    limit: int = 50,
    username: str | None = None,
) -> str:
    """List liked TV seasons as TSV. Routes to configured media tracker (TRACKED_MEDIA_SOURCE env var). Errors as strings."""
    tracker = get_media_tracker()
    if tracker == "floppy":
        return _floppy_liked_tv_seasons(
            threshold_user_rating=threshold_user_rating,
            days=days,
            limit=limit,
        )
    else:  # trakt
        return _trakt_liked_tv_seasons(
            username=username,
            threshold_user_rating=threshold_user_rating,
            limit=limit,
        )


@log_tool_call
def get_disliked_movies(
    days: int = 30,
    limit: int = 50,
    username: str | None = None,
) -> str:
    """List disliked movies as TSV. Routes to configured media tracker (TRACKED_MEDIA_SOURCE env var). Errors as strings."""
    tracker = get_media_tracker()
    if tracker == "floppy":
        return _floppy_disliked_movies(days=days, limit=limit)
    else:  # trakt
        return _trakt_disliked_movies(username=username, limit=limit)


@log_tool_call
def get_disliked_tv_seasons(
    days: int = 30,
    limit: int = 50,
) -> str:
    """List disliked TV seasons as TSV. Routes to configured media tracker (TRACKED_MEDIA_SOURCE env var). Errors as strings."""
    tracker = get_media_tracker()
    if tracker == "floppy":
        return _floppy_disliked_tv_seasons(days=days, limit=limit)
    else:  # trakt
        return "Error: Disliked TV shows are not available for Trakt tracker"


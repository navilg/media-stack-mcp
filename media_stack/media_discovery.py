"""Discovery and search router tools that route to either TMDB or Trakt based on configuration."""

from media_stack.config import get_discovery_source
from media_stack.logging_util import log_tool_call

# Import TMDB tools needed for routing
from media_stack.tmdb import (
    get_tmdb_trending_movies as _tmdb_trending_movies,
    get_tmdb_trending_shows as _tmdb_trending_shows,
    get_tmdb_popular_movies as _tmdb_popular_movies,
    get_tmdb_popular_shows as _tmdb_popular_shows,
    get_tmdb_latest_high_rated_movies as _tmdb_high_rated_movies,
    get_tmdb_latest_high_rated_shows as _tmdb_high_rated_shows,
    search_tmdb_movie_by_title as _tmdb_search_movie,
    search_tmdb_tv_show_by_title as _tmdb_search_tv_show,
    get_tmdb_movie_details as _tmdb_movie_details,
    get_tmdb_tv_show_details as _tmdb_tv_show_details,
)

# Import trakt tools needed for routing
from media_stack.trakt import (
    get_trakt_trending_movies as _trakt_trending_movies,
    get_trakt_trending_shows as _trakt_trending_shows,
    get_trakt_popular_movies as _trakt_popular_movies,
    get_trakt_popular_shows as _trakt_popular_shows,
    get_trakt_latest_high_rated_movies as _trakt_high_rated_movies,
    get_trakt_latest_high_rated_shows as _trakt_high_rated_shows,
    search_trakt_movie_by_title as _trakt_search_movie,
    search_trakt_show_by_title as _trakt_search_tv_show,
)


@log_tool_call
def get_trending_movies(limit: int = 50) -> str:
    """List trending movies as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_trending_movies(limit=limit)
    else:  # trakt
        return _trakt_trending_movies(limit=limit)


@log_tool_call
def get_trending_shows(limit: int = 50) -> str:
    """List trending TV shows as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_trending_shows(limit=limit)
    else:  # trakt
        return _trakt_trending_shows(limit=limit)


@log_tool_call
def get_popular_movies(limit: int = 50) -> str:
    """List popular movies as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_popular_movies(limit=limit)
    else:  # trakt
        return _trakt_popular_movies(limit=limit)


@log_tool_call
def get_popular_shows(limit: int = 50) -> str:
    """List popular TV shows as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_popular_shows(limit=limit)
    else:  # trakt
        return _trakt_popular_shows(limit=limit)


@log_tool_call
def get_high_rated_movies(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """List high-rated movies as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_high_rated_movies(days=days, threshold_rating=threshold_rating, limit=limit)
    else:  # trakt
        return _trakt_high_rated_movies(days=days, threshold_rating=threshold_rating, limit=limit)


@log_tool_call
def get_high_rated_shows(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """List high-rated TV shows as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_high_rated_shows(days=days, threshold_rating=threshold_rating, limit=limit)
    else:  # trakt
        return _trakt_high_rated_shows(days=days, threshold_rating=threshold_rating, limit=limit)


@log_tool_call
def search_movie_by_title(
    title: str,
    year: int | None = None,
    limit: int = 5,
) -> str:
    """Search for movies by title as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_search_movie(title=title, year=year, limit=limit)
    else:  # trakt
        return _trakt_search_movie(title=title, year=year, limit=limit)


@log_tool_call
def search_tv_show_by_title(
    title: str,
    year: int | None = None,
    limit: int = 5,
) -> str:
    """Search for TV shows by title as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_search_tv_show(title=title, year=year, limit=limit)
    else:  # trakt
        return _trakt_search_tv_show(title=title, year=year, limit=limit)


@log_tool_call
def get_movie_details(
    media_id: str,
) -> str:
    """Get movie details as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_movie_details(tmdb_id=media_id)
    else:  # trakt - not supported
        return "Error: Trakt does not support get_movie_details. Use TMDB as MEDIA_DISCOVERY_SOURCE instead."


@log_tool_call
def get_tv_show_details(
    media_id: str,
) -> str:
    """Get TV show details as TSV. Routes to configured discovery source (MEDIA_DISCOVERY_SOURCE env var). Errors as strings."""
    source = get_discovery_source()
    if source == "tmdb":
        return _tmdb_tv_show_details(tmdb_id=media_id)
    else:  # trakt - not supported
        return "Error: Trakt does not support get_tv_show_details. Use TMDB as MEDIA_DISCOVERY_SOURCE instead."

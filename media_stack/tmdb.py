import os
import time
from datetime import datetime, timedelta, timezone

import requests

from media_stack.constants import TMDB_API_BASE
from media_stack.formatting import to_tsv


def _get_tmdb_headers() -> dict[str, str] | str:
    """Get TMDB API headers with bearer token."""
    tmdb_api_key = os.getenv("TMDB_API_KEY")
    if not tmdb_api_key:
        return "Error: TMDB_API_KEY is not set"

    return {
        "Authorization": f"Bearer {tmdb_api_key}",
        "Accept": "application/json",
    }


def _get_latest_season_air_date(show_id: int, headers: dict, max_retries: int = 10, base_delay: int = 1) -> str | None:
    """Get the air date of the latest season for a TV show.
    
    Args:
        show_id: TMDB TV show ID
        headers: HTTP headers with authentication
        max_retries: Maximum retry attempts
        base_delay: Initial delay for exponential backoff
        
    Returns:
        Air date string (YYYY-MM-DD) or None if not found or error occurs
    """
    endpoint = f"{TMDB_API_BASE}/tv/{show_id}"
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = requests.get(endpoint, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            seasons = data.get("seasons", [])
            if seasons:
                # Find the latest season (highest season number that's not a special season)
                latest_season = None
                for season in sorted(seasons, key=lambda s: s.get("season_number", -1), reverse=True):
                    if season.get("season_number", 0) >= 0:  # Skip specials (season 0)
                        latest_season = season
                        break
                
                if latest_season:
                    return latest_season.get("air_date")
            
            return None
            
        except (requests.RequestException, ValueError):
            retry_count += 1
            if retry_count >= max_retries:
                return None
            delay = base_delay * (2 ** (retry_count - 1))
            time.sleep(delay)


def get_tmdb_latest_high_rated_movies(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """List recent TMDB movies meeting `threshold_rating` as TSV (`days` > 0; errors as strings).
    
    Loops through paginated results until reaching the total limit or exhausting all pages.
    Retries up to 10 times on transient failures with exponential backoff.
    """
    headers = _get_tmdb_headers()

    if isinstance(headers, str):
        return headers
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now_utc.strftime("%Y-%m-%d")

    endpoint = f"{TMDB_API_BASE}/discover/movie"
    params = {
        "include_adult": False,
        "include_video": False,
        "page": 1,
        "primary_release_date.gte": start_date,
        "primary_release_date.lte": end_date,
        "sort_by": "popularity.desc",
        "vote_average.gte": threshold_rating,
        "vote_count.gte": 50,
    }

    all_movies: list[dict] = []
    max_retries = 10
    base_delay = 1  # Start with 1 second

    try:
        while len(all_movies) < limit:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = requests.get(endpoint, params=params, headers=headers, timeout=20)
                    response.raise_for_status()
                    data = response.json()
                    break
                except (requests.RequestException, ValueError) as exc:
                    retry_count += 1
                    if retry_count >= max_retries:
                        return f"Error: Failed to fetch latest movies from TMDB after {max_retries} retries: {exc}"
                    delay = base_delay * (2 ** (retry_count - 1))
                    time.sleep(delay)

            movies_data = data.get("results", [])
            if not movies_data:
                break

            for movie in movies_data:
                if len(all_movies) >= limit:
                    break

                all_movies.append(
                    {
                        "title": movie.get("title"),
                        "release_date": movie.get("release_date"),
                        "average_rating": round(movie.get("vote_average", 0), 2),
                        "vote_count": movie.get("vote_count"),
                        "popularity": round(movie.get("popularity", 0), 2),
                        "genre_ids": ",".join(str(g) for g in movie.get("genre_ids", [])),
                        "original_language": movie.get("original_language"),
                        "overview": movie.get("overview", "")[:100],  # Truncate long overviews
                        "tmdb_id": movie.get("id"),
                    }
                )

            total_pages = data.get("total_pages", 1)
            if params["page"] >= total_pages:
                break

            params["page"] += 1

    except requests.RequestException as exc:
        return f"Error: Failed to fetch latest movies from TMDB: {exc}"

    return to_tsv(all_movies)


def get_tmdb_latest_high_rated_shows(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """List recent TMDB TV shows by latest season air date, meeting `threshold_rating` as TSV (`days` > 0; errors as strings).
    
    Loops through paginated results until reaching the total limit or exhausting all pages.
    Fetches latest season premiere date for each show. Retries up to 10 times on transient 
    failures with exponential backoff.
    
    Args:
        days: Look back N days from today (must be > 0)
        threshold_rating: Minimum vote average filter
        limit: Maximum number of shows to return
    """
    headers = _get_tmdb_headers()

    if isinstance(headers, str):
        return headers
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now_utc.strftime("%Y-%m-%d")

    endpoint = f"{TMDB_API_BASE}/discover/tv"
    params = {
        "include_adult": False,
        "page": 1,
        "first_air_date.gte": start_date,
        "first_air_date.lte": end_date,
        "sort_by": "popularity.desc",
        "vote_average.gte": threshold_rating,
        "vote_count.gte": 50,
    }

    all_shows: list[dict] = []
    max_retries = 10
    base_delay = 1  # Start with 1 second

    try:
        while len(all_shows) < limit:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = requests.get(endpoint, params=params, headers=headers, timeout=20)
                    response.raise_for_status()
                    data = response.json()
                    break
                except (requests.RequestException, ValueError) as exc:
                    retry_count += 1
                    if retry_count >= max_retries:
                        return f"Error: Failed to fetch latest shows from TMDB after {max_retries} retries: {exc}"
                    delay = base_delay * (2 ** (retry_count - 1))
                    time.sleep(delay)

            shows_data = data.get("results", [])
            if not shows_data:
                break

            for show in shows_data:
                if len(all_shows) >= limit:
                    break

                show_id = show.get("id")

                # Always fetch latest season air date
                season_air_date = _get_latest_season_air_date(show_id, headers, max_retries, base_delay)
                if not season_air_date:
                    # If we can't fetch season info, skip this show
                    continue

                all_shows.append(
                    {
                        "name": show.get("name"),
                        "latest_air_date": season_air_date,
                        "average_rating": round(show.get("vote_average", 0), 2),
                        "vote_count": show.get("vote_count"),
                        "popularity": round(show.get("popularity", 0), 2),
                        "genre_ids": ",".join(str(g) for g in show.get("genre_ids", [])),
                        "original_language": show.get("original_language"),
                        "overview": show.get("overview", "")[:100],  # Truncate long overviews
                        "tmdb_id": show_id,
                    }
                )

            total_pages = data.get("total_pages", 1)
            if params["page"] >= total_pages:
                break

            params["page"] += 1

    except requests.RequestException as exc:
        return f"Error: Failed to fetch latest shows from TMDB: {exc}"

    return to_tsv(all_shows)


def get_tmdb_trending_movies(
    limit: int = 50,
    time_window: str = "week",
) -> str:
    """List trending TMDB movies as TSV.
    
    Loops through paginated results until reaching the total limit or exhausting all pages.
    Retries up to 10 times on transient failures with exponential backoff.
    
    Args:
        limit: Maximum number of movies to return (default 50)
        time_window: Time window for trending (day or week; default week)
    """
    headers = _get_tmdb_headers()

    if isinstance(headers, str):
        return headers
    if limit <= 0:
        return "Error: limit must be greater than 0"
    if time_window not in ("day", "week"):
        return "Error: time_window must be 'day' or 'week'"

    endpoint = f"{TMDB_API_BASE}/trending/movie/{time_window}"
    params = {
        "page": 1,
    }

    all_movies: list[dict] = []
    max_retries = 10
    base_delay = 1  # Start with 1 second

    try:
        while len(all_movies) < limit:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = requests.get(endpoint, params=params, headers=headers, timeout=20)
                    response.raise_for_status()
                    data = response.json()
                    break
                except (requests.RequestException, ValueError) as exc:
                    retry_count += 1
                    if retry_count >= max_retries:
                        return f"Error: Failed to fetch trending movies from TMDB after {max_retries} retries: {exc}"
                    delay = base_delay * (2 ** (retry_count - 1))
                    time.sleep(delay)

            movies_data = data.get("results", [])
            if not movies_data:
                break

            for movie in movies_data:
                if len(all_movies) >= limit:
                    break

                all_movies.append(
                    {
                        "title": movie.get("title"),
                        "release_date": movie.get("release_date"),
                        "average_rating": round(movie.get("vote_average", 0), 2),
                        "vote_count": movie.get("vote_count"),
                        "popularity": round(movie.get("popularity", 0), 2),
                        "genre_ids": ",".join(str(g) for g in movie.get("genre_ids", [])),
                        "original_language": movie.get("original_language"),
                        "overview": movie.get("overview", "")[:100],  # Truncate long overviews
                        "tmdb_id": movie.get("id"),
                    }
                )

            total_pages = data.get("total_pages", 1)
            if params["page"] >= total_pages:
                break

            params["page"] += 1

    except requests.RequestException as exc:
        return f"Error: Failed to fetch trending movies from TMDB: {exc}"

    return to_tsv(all_movies)


def get_tmdb_trending_shows(
    limit: int = 50,
    time_window: str = "week",
) -> str:
    """List trending TMDB TV shows by latest season air date as TSV.
    
    Loops through paginated results until reaching the total limit or exhausting all pages.
    Retries up to 10 times on transient failures with exponential backoff.
    
    Args:
        limit: Maximum number of shows to return (default 50)
        time_window: Time window for trending (day or week; default week)
    """
    headers = _get_tmdb_headers()

    if isinstance(headers, str):
        return headers
    if limit <= 0:
        return "Error: limit must be greater than 0"
    if time_window not in ("day", "week"):
        return "Error: time_window must be 'day' or 'week'"

    endpoint = f"{TMDB_API_BASE}/trending/tv/{time_window}"
    params = {
        "page": 1,
    }

    all_shows: list[dict] = []
    max_retries = 10
    base_delay = 1  # Start with 1 second

    try:
        while len(all_shows) < limit:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = requests.get(endpoint, params=params, headers=headers, timeout=20)
                    response.raise_for_status()
                    data = response.json()
                    break
                except (requests.RequestException, ValueError) as exc:
                    retry_count += 1
                    if retry_count >= max_retries:
                        return f"Error: Failed to fetch trending shows from TMDB after {max_retries} retries: {exc}"
                    delay = base_delay * (2 ** (retry_count - 1))
                    time.sleep(delay)

            shows_data = data.get("results", [])
            if not shows_data:
                break

            for show in shows_data:
                if len(all_shows) >= limit:
                    break

                show_id = show.get("id")

                # Always fetch latest season air date
                season_air_date = _get_latest_season_air_date(show_id, headers, max_retries, base_delay)
                if not season_air_date:
                    # If we can't fetch season info, skip this show
                    continue

                all_shows.append(
                    {
                        "name": show.get("name"),
                        "latest_air_date": season_air_date,
                        "average_rating": round(show.get("vote_average", 0), 2),
                        "vote_count": show.get("vote_count"),
                        "popularity": round(show.get("popularity", 0), 2),
                        "genre_ids": ",".join(str(g) for g in show.get("genre_ids", [])),
                        "original_language": show.get("original_language"),
                        "overview": show.get("overview", "")[:100],  # Truncate long overviews
                        "tmdb_id": show_id,
                    }
                )

            total_pages = data.get("total_pages", 1)
            if params["page"] >= total_pages:
                break

            params["page"] += 1

    except requests.RequestException as exc:
        return f"Error: Failed to fetch trending shows from TMDB: {exc}"

    return to_tsv(all_shows)

from datetime import datetime, timedelta, timezone

import requests

from media_stack.config import get_floppy_config
from media_stack.formatting import to_tsv


def get_floppy_movie_details(media_id: str, source: str = "tmdb") -> dict:
    """Get detailed information for a specific movie from the authenticated user's Floppy account.
    INPUT: movie_id (str), source (str, default "tmdb"),
    OUTPUT: Dictionary containing movie details, or Error string.
    """
    config = get_floppy_config()
    if isinstance(config, str):
        return {"error": config}
    floppy_url, api_key = config

    try:
        response = requests.get(
            f"{floppy_url}/api/v1/media/movie/{source}/{media_id}/",
            headers={"X-API-Key": api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        fields_to_remove = (
            "id", "source_url", "max_progress", "episodes_left",
            "total_episodes_left", "image", "backdrop", "cast",
            "crew", "related", "item_id", "parent_id", "tracked",
            "consumptions_number", "consumptions", "lists", "media_type_status"
        )
        for key in fields_to_remove:
            payload.pop(key, None)
        return payload
    except requests.RequestException as exc:
        return {"error": f"Error: Failed to fetch movie details from Floppy: {exc}"}
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"error": "Error: Invalid response from Floppy"}


def get_floppy_watched_movies(days: int = 30, limit: int = 200) -> str:
    """Get movie consumption history from the authenticated user's Floppy account.
    INPUT: days (>0, default 30), limit (1-200, default 200).
    OUTPUT: TSV rows for completed movie history, or Error string.
    """
    if days <= 0:
        return "Error: days must be greater than 0"
    if limit <= 0 or limit > 200:
        return "Error: limit must be between 1 and 200"

    config = get_floppy_config()
    if isinstance(config, str):
        return config
    floppy_url, api_key = config

    now_utc = datetime.now(timezone.utc)
    params = {
        "flat": "1",
        "media_type": "movie",
        "start_date": (now_utc - timedelta(days=days)).date().isoformat(),
        "end_date": now_utc.date().isoformat(),
        "limit": limit,
        "offset": 0,
    }

    try:
        response = requests.get(
            f"{floppy_url}/api/v1/history/",
            params=params,
            headers={"X-API-Key": api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        watched_movies: list[dict] = []
        for entry in payload["results"]:
            status = entry.get("status")
            if not (
                status == 3
                or isinstance(status, str) and status.strip().casefold() == "completed"
            ):
                continue
            item = entry.get("item") or entry.get("media") or {}
            details = item.get("details") or {}
            watched_movies.append(
                {
                    "watched_at": entry.get("played_at_local"),
                    "title": entry.get("display_title") or entry.get("title") or item.get("title"),
                    "year": item.get("year") or details.get("year"),
                    "user_rating": entry.get("score"),
                    "genre": entry.get("genres") or item.get("genres") or details.get("genres"),
                    "play_count": entry.get("play_count"),
                }
            )
    except requests.RequestException as exc:
        return f"Error: Failed to fetch watched movies from Floppy: {exc}"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "Error: Invalid response from Floppy"

    return to_tsv(watched_movies)


def get_floppy_liked_movies(
        threshold_user_rating: int = 7,
        days: int = 30,
        limit: int = 50,
) -> str:
    """Get liked movies from the authenticated user's Floppy library.
    INPUT: limit (1-200, default 50), threshold_user_rating (default 7), days (default 30).
    OUTPUT: TSV rows ordered by Floppy's liked sort, filtered by threshold_user_rating and within the last 'days' days, or Error string.
    """
    if limit <= 0 or limit > 200:
        return "Error: limit must be between 1 and 200"

    config = get_floppy_config()
    if isinstance(config, str):
        return config
    floppy_url, api_key = config

    now_utc = datetime.now(timezone.utc)
    params = {
        "completed_date_from": (now_utc - timedelta(days=days)).strftime("%Y-%m-%d"),
        "completed_date_to": now_utc.strftime("%Y-%m-%d"),
        "status": "3",
        "rating": "rated",
        "sort": "end_date",
        "direction": "desc",
        "limit": 200,
        "offset": 0,
    }
    movies: list[dict] = []

    try:
        while len(movies) < limit:
            response = requests.get(
                f"{floppy_url}/api/v1/media/movie/",
                params=params,
                headers={"X-API-Key": api_key},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            entries = payload["results"]
            for entry in entries:
                score = entry.get("score")
                if not isinstance(score, (int, float)) or score < threshold_user_rating:
                    continue
                item = entry.get("item") or {}
                movies.append(
                    {
                        "title": item.get("title"),
                        "year": item.get("release_datetime", "")[:4],
                        "runtime": item.get("runtime"),
                        "imdb_rating": item.get("imdb_rating"),
                        "provider_rating": item.get("provider_rating"),
                        "user_rating": score,
                        "genres": item.get("genres"),
                        "completed_date": entry.get("end_date"),
                        "certification": item.get("provider_certification"),
                        "language": (item.get("languages") or [""])[0],
                        "overview": item.get("synopsis"),
                    }
                )
                if len(movies) == limit:
                    break
            params["offset"] += len(entries)
            if not entries or params["offset"] >= payload["pagination"]["total"]:
                break
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return f"Error: Failed to fetch latest completed movies from Floppy: {exc}"

    return to_tsv(movies)

def get_floppy_disliked_movies(
        threshold_user_rating: int = 6,
        days: int = 30,
        limit: int = 50,
) -> str:
    """Get disliked movies from the authenticated user's Floppy library.
    INPUT: limit (1-200, default 50), threshold_user_rating (default 6), days (default 30).
    OUTPUT: TSV rows ordered by Floppy's disliked sort, filtered by threshold_user_rating (inclusive) and within the last 'days' days, or Error string.
    """
    if limit <= 0 or limit > 200:
        return "Error: limit must be between 1 and 200"

    config = get_floppy_config()
    if isinstance(config, str):
        return config
    floppy_url, api_key = config

    now_utc = datetime.now(timezone.utc)
    params = {
        "completed_date_from": (now_utc - timedelta(days=days)).strftime("%Y-%m-%d"),
        "completed_date_to": now_utc.strftime("%Y-%m-%d"),
        "status": "3",
        "rating": "rated",
        "sort": "end_date",
        "direction": "desc",
        "limit": 200,
        "offset": 0,
    }
    movies: list[dict] = []

    try:
        while len(movies) < limit:
            response = requests.get(
                f"{floppy_url}/api/v1/media/movie/",
                params=params,
                headers={"X-API-Key": api_key},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            entries = payload["results"]
            for entry in entries:
                score = entry.get("score")
                if not isinstance(score, (int, float)) or score >= threshold_user_rating:
                    continue
                item = entry.get("item") or {}
                movies.append(
                    {
                        "title": item.get("title"),
                        "year": item.get("release_datetime", "")[:4],
                        "runtime": item.get("runtime"),
                        "imdb_rating": item.get("imdb_rating"),
                        "provider_rating": item.get("provider_rating"),
                        "user_rating": score,
                        "genres": item.get("genres"),
                        "completed_date": entry.get("end_date"),
                        "certification": item.get("provider_certification"),
                        "language": (item.get("languages") or [""])[0],
                        "overview": item.get("synopsis"),
                    }
                )
                if len(movies) == limit:
                    break
            params["offset"] += len(entries)
            if not entries or params["offset"] >= payload["pagination"]["total"]:
                break
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return f"Error: Failed to fetch latest completed movies from Floppy: {exc}"

    return to_tsv(movies)

def get_floppy_trending_movies() -> str:
    """Get top 20 trending movies from Floppy.
    INPUT: None.
    OUTPUT: TSV rows ordered by Floppy's trending sort, or Error string.
    """
    limit = 20

    config = get_floppy_config()
    if isinstance(config, str):
        return config
    floppy_url, api_key = config

    params = {
        "media_type": "movie",
    }
    movies: list[dict] = []

    try:
        response = requests.get(
            f"{floppy_url}/api/v1/discover/",
            params=params,
            headers={"X-API-Key": api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload["rows"]
        for row in rows:
            key = row.get("key")
            if key != "trending_right_now":
                continue
            items = row.get("items") or []
            for item in items:
                movie = get_floppy_movie_details(media_id=item.get("media_id"), source=item.get("source"))
                movie_details = movie.get("details") or {}
                movies.append(
                    {
                        "title": item.get("title"),
                        "year": item.get("release_date", "")[:4],
                        "runtime": movie_details.get("runtime") or None,
                        "rating": item.get("rating") or None,
                        "genres": item.get("genres", []),
                        "certification": movie_details.get("certification") or None,
                        "language": (movie_details.get("languages") or [None])[0],
                        "overview": movie.get("synopsis"),
                    }
                )
                if len(movies) == limit:
                    break
            if key == "trending_right_now":
                break
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return f"Error: Failed to fetch trending movies from Floppy: {exc}"

    return to_tsv(movies)

def search_floppy_movie_by_title(title: str, limit: int = 5) -> str:
    """Search for movies on Floppy by title.
    INPUT: title (str), limit (int, default 5).
    OUTPUT: TSV rows of search results, or Error string.
    """
    config = get_floppy_config()
    if isinstance(config, str):
        return config
    floppy_url, api_key = config

    params = {
        "search": title,
        "limit": limit,
    }
    movies: list[dict] = []

    try:
        response = requests.get(
            f"{floppy_url}/api/v1/search/movie/",
            params=params,
            headers={"X-API-Key": api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("results") or []
        for item in items:
            movie = get_floppy_movie_details(media_id=item.get("media_id"), source=item.get("source"))
            movie_details = movie.get("details") or {}
            movies.append(
                {
                    "title": item.get("title"),
                    "year": item.get("year", ""),
                    "runtime": movie_details.get("runtime") or None,
                    "rating": movie.get("score") or None,
                    "genres": movie.get("genres", []),
                    "certification": movie_details.get("certification") or None,
                    "language": (movie_details.get("languages") or [None])[0],
                    "overview": movie.get("synopsis"),
                    "source": item.get("source"),
                }
            )
            if len(movies) == limit:
                break
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return f"Error: Failed to search movies on Floppy: {exc}"

    return to_tsv(movies)

def get_floppy_top_picks_movie(limit: int = 10) -> str:
    """Get top picks movies from Floppy.
    INPUT: limit (int, default 10).
    OUTPUT: TSV rows of top picks movies, or Error string.
    """
    config = get_floppy_config()
    if isinstance(config, str):
        return config
    floppy_url, api_key = config

    movies: list[dict] = []

    params = {
        "media_type": "movie",
    }

    try:
        response = requests.get(
            f"{floppy_url}/api/v1/discover/",
            params=params,
            headers={"X-API-Key": api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload["rows"]
        for row in rows:
            key = row.get("key")
            if key != "top_picks_for_you":
                continue
            items = row.get("items") or []
            for item in items:
                movie = get_floppy_movie_details(media_id=item.get("media_id"), source=item.get("source"))
                movie_details = movie.get("details") or {}
                movies.append(
                    {
                        "title": item.get("title"),
                        "year": item.get("release_date", "")[:4],
                        "runtime": movie_details.get("runtime") or None,
                        "rating": item.get("rating") or None,
                        "genres": item.get("genres", []),
                        "certification": movie_details.get("certification") or None,
                        "language": (movie_details.get("languages") or [None])[0],
                        "overview": movie.get("synopsis"),
                    }
                )
                if len(movies) == limit:
                    break
            if key == "top_picks_for_you":
                break
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return f"Error: Failed to fetch top picks movies from Floppy: {exc}"

    return to_tsv(movies)
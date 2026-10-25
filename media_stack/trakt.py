import os
from math import ceil
from datetime import datetime, timedelta, timezone

import requests

from media_stack.constants import TRAKT_API_BASE
from media_stack.formatting import to_tsv


def _resolve_username(username: str | None) -> str | None:
    return username or os.getenv("TRAKT_USERNAME")


def _get_trakt_headers() -> dict[str, str] | str:
    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"

    return {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": trakt_client_id,
    }


def check_trakt_profile_privacy(username: str | None = None) -> str:
    """Check Trakt profile visibility (`username` defaults to `TRAKT_USERNAME`); errors as strings."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"

    profile_url = f"{TRAKT_API_BASE}/users/{username}"
    try:
        profile_response = requests.get(
            profile_url,
            params={"extended": "full"},
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        return f"Error: Failed to check Trakt profile: {exc}"

    if profile_response.status_code == 404:
        return f"Trakt user {username} not found"

    if profile_response.ok:
        data = profile_response.json()
        is_private = data.get("private")
        if isinstance(is_private, bool):
            details = ""
            if is_private:
                details = "Make profile/history public in Trakt privacy settings to allow public access."
                profile_visibility = "private"
            else:
                profile_visibility = "public"

            return f"Trakt user {username}'s profile visibility is {profile_visibility}. {details}"

    history_url = f"{TRAKT_API_BASE}/users/{username}/history/movies"
    try:
        history_response = requests.get(
            history_url,
            params={"limit": "1"},
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        return f"Error: Failed to infer profile visibility from history endpoint: {exc}"

    if history_response.status_code == 200:
        return f"Trakt user {username}'s profile visibility is public."

    if history_response.status_code in (401, 403):
        return f"Trakt user {username}'s profile visibility is private. Make profile/history public in Trakt privacy settings to allow public access."

    return f"Error: Unexpected error. Status code: {history_response.status_code}"


def get_trakt_public_watched_movies(username: str | None = None, days: int = 30) -> str:
    """List public-profile movies watched within `days` as TSV (`days` > 0; errors as strings)."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    end_at = now_utc.isoformat().replace("+00:00", "Z")

    endpoint = f"{TRAKT_API_BASE}/users/{username}/history/movies"
    params = {
        "start_at": start_at,
        "end_at": end_at,
        "limit": "1000",
        "extended": "full",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public watched movies from Trakt: {exc}"

    history_items = response.json()
    watched_movies: list[dict] = []
    seen_movie_keys: set[str] = set()

    def _movie_key(movie: dict) -> str:
        ids = movie.get("ids", {}) if isinstance(movie, dict) else {}
        trakt_id = ids.get("trakt")
        if trakt_id is not None:
            return f"trakt:{trakt_id}"
        tmdb_id = ids.get("tmdb")
        if tmdb_id is not None:
            return f"tmdb:{tmdb_id}"
        imdb_id = ids.get("imdb")
        if imdb_id:
            return f"imdb:{imdb_id}"
        return f"title:{movie.get('title')}:{movie.get('year')}"

    for item in history_items:
        movie = item.get("movie", {})
        movie_key = _movie_key(movie)
        if movie_key in seen_movie_keys:
            continue
        seen_movie_keys.add(movie_key)

        watched_movies.append(
            {
                "watched_at": item.get("watched_at"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "rating": movie.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
            }
        )

    return to_tsv(watched_movies)


def get_trakt_public_watched_shows(username: str | None = None, days: int = 30) -> str:
    """List public-profile episodes watched within `days` as TSV (`days` > 0; errors as strings)."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    end_at = now_utc.isoformat().replace("+00:00", "Z")

    endpoint = f"{TRAKT_API_BASE}/users/{username}/history/shows"
    params = {
        "start_at": start_at,
        "end_at": end_at,
        "limit": "1000",
        "extended": "full",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public watched shows from Trakt: {exc}"

    history_items = response.json()
    season_episode_count_cache: dict[tuple[str, int], int | None] = {}

    def _get_season_episode_count(show_ids: dict, season_number: int | None) -> int | None:
        if not isinstance(season_number, int):
            return None

        show_slug = show_ids.get("slug") if isinstance(show_ids, dict) else None
        if not show_slug:
            return None

        cache_key = (show_slug, season_number)
        if cache_key in season_episode_count_cache:
            return season_episode_count_cache[cache_key]

        season_endpoint = f"{TRAKT_API_BASE}/shows/{show_slug}/seasons/{season_number}"
        season_params = {"extended": "episodes"}

        try:
            season_response = requests.get(season_endpoint, params=season_params, headers=headers, timeout=20)
            season_response.raise_for_status()
        except requests.RequestException:
            season_episode_count_cache[cache_key] = None
            return None

        season_payload = season_response.json()
        if isinstance(season_payload, list) and season_payload:
            season_payload = season_payload[0]

        episodes = season_payload.get("episodes", []) if isinstance(season_payload, dict) else []
        total_episodes = len(episodes) if isinstance(episodes, list) else None
        season_episode_count_cache[cache_key] = total_episodes
        return total_episodes

    watched_shows: list[dict] = []
    seen_show_episode_keys: set[str] = set()

    def _show_episode_key(show: dict, season_number: int | None, episode_number: int | None) -> str:
        ids = show.get("ids", {}) if isinstance(show, dict) else {}
        trakt_id = ids.get("trakt")
        if trakt_id is not None:
            show_key = f"trakt:{trakt_id}"
        else:
            slug = ids.get("slug")
            if slug:
                show_key = f"slug:{slug}"
            else:
                show_key = f"title:{show.get('title')}:{show.get('year')}"
        return f"{show_key}|season:{season_number}|episode:{episode_number}"

    for item in history_items:
        show = item.get("show", {})
        episode = item.get("episode", {})

        season_number = episode.get("season")
        episode_number = episode.get("number")
        show_episode_key = _show_episode_key(show, season_number, episode_number)
        if show_episode_key in seen_show_episode_keys:
            continue
        seen_show_episode_keys.add(show_episode_key)

        season_episode_count = _get_season_episode_count(show.get("ids", {}), season_number)

        episode_position = None
        if isinstance(episode_number, int):
            if isinstance(season_episode_count, int) and season_episode_count > 0:
                episode_position = f"{episode_number}/{season_episode_count}"
            else:
                episode_position = str(episode_number)

        watched_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "season": season_number,
                "episode_position": episode_position,
                "watched_at": item.get("watched_at"),
                "episode_rating": episode.get("rating"),
                "show_rating": show.get("rating"),
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
            }
        )

    return to_tsv(watched_shows)


def get_trakt_public_liked_movies(
    username: str | None = None,
    threshold_user_rating: int = 7,
    limit: int = 50,
) -> str:
    """List public-profile movies rated >= `threshold_user_rating` as TSV; errors as strings."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"

    rating = ",".join(str(rating_value) for rating_value in range(threshold_user_rating, 11))
    endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/movies/{rating}"
    params = {"limit": str(limit), "extended": "full"}

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public liked movies from Trakt: {exc}"

    liked_items = response.json()
    liked_movies: list[dict] = []
    for item in liked_items:
        movie = item.get("movie", {})
        liked_movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": movie.get("rating"),
                "user_rating": item.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(liked_movies)


def get_trakt_public_liked_shows(
    username: str | None = None,
    threshold_user_rating: float = 7.5,
    limit: int = 50,
) -> str:
    """List public-profile shows rated >= `threshold_user_rating` or fully watched,
    ordered by latest watch; TSV output (rating 1-10, limit > 0), errors as strings.
    """
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"
    if limit <= 0:
        return "Error: limit must be greater than 0"
    if threshold_user_rating < 1 or threshold_user_rating > 10:
        return "Error: threshold_user_rating must be between 1 and 10"

    min_rating = ceil(threshold_user_rating)
    ratings = ",".join(str(rating_value) for rating_value in range(min_rating, 11))

    ratings_endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/shows/{ratings}"
    watched_endpoint = f"{TRAKT_API_BASE}/users/{username}/watched/shows"

    try:
        rated_response = requests.get(
            ratings_endpoint,
            params={"limit": "1000", "extended": "full"},
            headers=headers,
            timeout=20,
        )
        rated_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public liked shows from Trakt ratings: {exc}"

    try:
        watched_response = requests.get(
            watched_endpoint,
            params={"extended": "full"},
            headers=headers,
            timeout=20,
        )
        watched_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public watched shows from Trakt: {exc}"

    rated_items = rated_response.json()
    watched_items = watched_response.json()

    def _show_key(show: dict) -> str:
        ids = show.get("ids", {}) if isinstance(show, dict) else {}
        trakt_id = ids.get("trakt")
        if trakt_id is not None:
            return f"trakt:{trakt_id}"
        slug = ids.get("slug")
        if slug:
            return f"slug:{slug}"
        return f"title:{show.get('title')}:{show.get('year')}"

    watched_latest_map: dict[str, str | None] = {}
    fully_watched_map: dict[str, dict] = {}
    for item in watched_items:
        show = item.get("show", {})
        key = _show_key(show)
        last_watched_at = item.get("last_watched_at")
        watched_latest_map[key] = last_watched_at

        aired = item.get("aired")
        completed = item.get("completed")
        is_fully_watched = (
            isinstance(aired, int)
            and isinstance(completed, int)
            and aired > 0
            and completed >= aired
        )
        if is_fully_watched:
            fully_watched_map[key] = {
                "show": show,
                "latest_watched_at": last_watched_at,
            }

    merged: dict[str, dict] = {}

    for item in rated_items:
        show = item.get("show", {})
        key = _show_key(show)
        reason = "rated_7.5+"
        if threshold_user_rating != 7.5:
            reason = f"rated_{threshold_user_rating}+"

        merged[key] = {
            "title": show.get("title"),
            "year": show.get("year"),
            "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
            "average_rating": show.get("rating"),
            "user_rating": item.get("rating"),
            "latest_watched_at": watched_latest_map.get(key) or item.get("rated_at"),
            "genre": show.get("genres", []),
            "certification": show.get("certification"),
            "language": show.get("language"),
            "network": show.get("network"),
            "overview": show.get("overview"),
            "liked_consideration": {reason},
        }

    for key, watched_data in fully_watched_map.items():
        show = watched_data.get("show", {})
        latest_watched_at = watched_data.get("latest_watched_at")
        if key in merged:
            merged[key]["liked_consideration"].add("watched_all_aired_episodes")
            if latest_watched_at and not merged[key].get("latest_watched_at"):
                merged[key]["latest_watched_at"] = latest_watched_at
            continue

        merged[key] = {
            "title": show.get("title"),
            "year": show.get("year"),
            "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
            "average_rating": show.get("rating"),
            "user_rating": None,
            "latest_watched_at": latest_watched_at,
            "genre": show.get("genres", []),
            "certification": show.get("certification"),
            "language": show.get("language"),
            "network": show.get("network"),
            "overview": show.get("overview"),
            "liked_consideration": {"watched_all_aired_episodes"},
        }

    liked_shows = list(merged.values())
    for item in liked_shows:
        reasons = sorted(item.get("liked_consideration", set()))
        item["liked_consideration"] = ",".join(reasons)

    liked_shows.sort(key=lambda item: item.get("latest_watched_at") or "", reverse=True)
    return to_tsv(liked_shows[:limit])


def get_trakt_public_disliked_movies(
    username: str | None = None,
    threshold_user_rating: int = 6,
    limit: int = 50,
) -> str:
    """List public-profile movies rated < `threshold_user_rating` as TSV; errors as strings."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"

    rating = ",".join(str(rating_value) for rating_value in range(1, threshold_user_rating))
    endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/movies/{rating}"
    params = {"limit": str(limit), "extended": "full"}

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public disliked movies from Trakt: {exc}"

    disliked_items = response.json()
    disliked_movies: list[dict] = []
    for item in disliked_items:
        movie = item.get("movie", {})
        disliked_movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": movie.get("rating"),
                "user_rating": item.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(disliked_movies)


def get_trakt_latest_high_rated_movies(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """List recent Trakt movies meeting `threshold_rating` as TSV (`days` > 0; errors as strings)."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")

    endpoint = f"{TRAKT_API_BASE}/calendars/all/movies/{start_at}/{days}"
    params = {
        "extended": "full",
        "ratings": f"{int(threshold_rating * 10)}-100",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch latest movies from Trakt: {exc}"

    movies_data = response.json()[:limit]
    latest_movies: list[dict] = []
    for item in movies_data:
        movie = item.get("movie", {})
        latest_movies.append(
            {
                "title": movie.get("title"),
                "release_date": movie.get("released"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2)
                if isinstance(movie.get("rating"), (int, float))
                else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(latest_movies)


def get_trakt_latest_high_rated_shows(
    days: int = 30,
    threshold_rating: float = 7.5,
    limit: int = 50,
) -> str:
    """List recent Trakt shows meeting `threshold_rating` as TSV (`days` > 0; errors as strings)."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")

    endpoint = f"{TRAKT_API_BASE}/calendars/all/shows/{start_at}/{days}"
    params = {
        "extended": "full",
        "ratings": f"{int(threshold_rating * 10)}-100",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch latest shows from Trakt: {exc}"

    shows_data = response.json()[:limit]
    latest_shows: list[dict] = []
    for item in shows_data:
        show = item.get("show", {})
        latest_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "first_aired": item.get("first_aired"),
                "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
                "average_rating": round(show.get("rating"), 2)
                if isinstance(show.get("rating"), (int, float))
                else None,
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
                "network": show.get("network"),
                "overview": show.get("overview"),
            }
        )

    return to_tsv(latest_shows)


def get_trakt_popular_shows(limit: int = 50) -> str:
    """List popular Trakt shows as TSV; errors as strings."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers

    endpoint = f"{TRAKT_API_BASE}/shows/popular"
    params = {"extended": "full"}

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch popular shows from Trakt: {exc}"

    shows_data = response.json()[:limit]
    popular_shows: list[dict] = []
    for show in shows_data:
        popular_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
                "average_rating": round(show.get("rating"), 2)
                if isinstance(show.get("rating"), (int, float))
                else None,
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
                "network": show.get("network"),
                "overview": show.get("overview"),
            }
        )

    return to_tsv(popular_shows)


def get_trakt_trending_movies() -> str:
    """List up to 20 trending Trakt movies as TSV; errors as strings."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers

    endpoint = f"{TRAKT_API_BASE}/movies/trending"
    params = {
        "extended": "full",
        "limit": "20",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch trending movies from Trakt: {exc}"

    trending_data = response.json()[:20]
    trending_movies: list[dict] = []
    for item in trending_data:
        movie = item.get("movie", {})
        trending_movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "watchers": item.get("watchers"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2)
                if isinstance(movie.get("rating"), (int, float))
                else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(trending_movies)


def get_trakt_trending_shows() -> str:
    """List up to 20 trending Trakt shows as TSV; errors as strings."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers

    endpoint = f"{TRAKT_API_BASE}/shows/trending"
    params = {
        "extended": "full",
        "limit": "20",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch trending shows from Trakt: {exc}"

    trending_data = response.json()[:20]
    trending_shows: list[dict] = []
    for item in trending_data:
        show = item.get("show", {})
        trending_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "watchers": item.get("watchers"),
                "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
                "average_rating": round(show.get("rating"), 2)
                if isinstance(show.get("rating"), (int, float))
                else None,
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
                "network": show.get("network"),
                "overview": show.get("overview"),
            }
        )

    return to_tsv(trending_shows)


def get_trakt_popular_movies(limit: int = 50) -> str:
    """List popular Trakt movies as TSV; errors as strings."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers

    endpoint = f"{TRAKT_API_BASE}/movies/popular"
    params = {"extended": "full"}

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch popular movies from Trakt: {exc}"

    movies_data = response.json()[:limit]
    popular_movies: list[dict] = []
    for movie in movies_data:
        popular_movies.append(
            {
                "title": movie.get("title"),
                "release_date": movie.get("released"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2)
                if isinstance(movie.get("rating"), (int, float))
                else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(popular_movies)


def search_trakt_movie_by_title(title: str, limit: int = 5) -> str:
    """Search Trakt movies by title; TSV matches (title required, limit > 0), errors as strings."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not title or not title.strip():
        return "Error: title must not be empty"
    if limit <= 0:
        return "Error: limit must be greater than 0"

    endpoint = f"{TRAKT_API_BASE}/search/movie"
    params = {
        "query": title.strip(),
        "extended": "full",
        "limit": str(limit),
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to search movies in Trakt: {exc}"

    search_data = response.json()
    matched_movies: list[dict] = []
    for item in search_data:
        movie = item.get("movie", {}) if isinstance(item, dict) else {}
        ids = movie.get("ids", {}) if isinstance(movie, dict) else {}
        rating = movie.get("rating") if isinstance(movie, dict) else None
        matched_movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "release_date": movie.get("released"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(rating, 2) if isinstance(rating, (int, float)) else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "trakt_id": ids.get("trakt"),
                "tmdb_id": ids.get("tmdb"),
                "imdb_id": ids.get("imdb"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(matched_movies)


def search_trakt_show_by_title(title: str, limit: int = 5) -> str:
    """Search Trakt shows by title; TSV matches (title required, limit > 0), errors as strings."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not title or not title.strip():
        return "Error: title must not be empty"
    if limit <= 0:
        return "Error: limit must be greater than 0"

    endpoint = f"{TRAKT_API_BASE}/search/show"
    params = {
        "query": title.strip(),
        "extended": "full",
        "limit": str(limit),
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to search shows in Trakt: {exc}"

    search_data = response.json()
    matched_shows: list[dict] = []
    for item in search_data:
        show = item.get("show", {}) if isinstance(item, dict) else {}
        ids = show.get("ids", {}) if isinstance(show, dict) else {}
        rating = show.get("rating") if isinstance(show, dict) else None
        matched_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "first_aired": show.get("first_aired"),
                "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
                "average_rating": round(rating, 2) if isinstance(rating, (int, float)) else None,
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
                "network": show.get("network"),
                "trakt_id": ids.get("trakt"),
                "tmdb_id": ids.get("tmdb"),
                "imdb_id": ids.get("imdb"),
                "tvdb_id": ids.get("tvdb"),
                "overview": show.get("overview"),
            }
        )

    return to_tsv(matched_shows)

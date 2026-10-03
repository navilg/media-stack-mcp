from datetime import datetime, timedelta, timezone

import requests

from media_stack.config import get_floppy_config
from media_stack.formatting import to_tsv


def get_floppy_latest_high_rated_movies(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """Get recently completed movies with high personal ratings from Floppy.
    INPUT: days (>0, default 30), threshold_rating (0-10, default 7), limit (>0, default 50).
    OUTPUT: TSV rows newest completion first, or Error string. Dates and ratings
    refer to your tracked consumption, not the movie's release or provider rating.
    """
    if days <= 0:
        return "Error: days must be greater than 0"
    if not 0 <= threshold_rating <= 10:
        return "Error: threshold_rating must be between 0 and 10"
    if limit <= 0:
        return "Error: limit must be greater than 0"

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
                if not isinstance(score, (int, float)) or score < threshold_rating:
                    continue
                item = entry.get("item") or {}
                movies.append(
                    {
                        "title": item.get("title"),
                        "media_id": item.get("media_id"),
                        "source": item.get("source"),
                        "consumption_id": entry.get("consumption_id"),
                        "completed_date": entry.get("end_date"),
                        "user_rating": score,
                        "notes": entry.get("notes"),
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
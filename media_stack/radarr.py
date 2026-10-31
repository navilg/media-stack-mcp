import requests

from media_stack.config import get_radarr_config
from media_stack.filters import normalize_library_filter
from media_stack.formatting import to_tsv
from media_stack.logging_util import log_tool_call


@log_tool_call
def get_radarr_movies(
    full_details: bool = False,
    title: str | None = None,
    filter: dict[str, object] | None = None,
) -> str:
    """List Radarr movies as TSV; `full_details` adds metadata. Filter by case-insensitive
    partial title and/or `monitored`, `has_file`, exact `genre`, or exact `certification`
    (case-insensitive; string filters trim whitespace). Filters combine with AND.
    Empty matches return `Empty list`; failures return an error string.
    """
    if title is not None and not title.strip():
        return "Error: title must not be empty"
    normalized_title = title.strip().lower() if title is not None else None

    normalized_filter = normalize_library_filter(filter)
    if isinstance(normalized_filter, str):
        return normalized_filter

    radarr_config = get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/movie"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch movies from Radarr: {exc}"

    movies_data = response.json()
    movies: list[dict] = []
    for movie in movies_data:
        if normalized_title is not None and normalized_title not in (
            movie.get("title") or ""
        ).lower():
            continue

        if (
            "monitored" in normalized_filter
            and movie.get("monitored") is not normalized_filter["monitored"]
        ):
            continue
        if (
            "has_file" in normalized_filter
            and movie.get("hasFile") is not normalized_filter["has_file"]
        ):
            continue
        if "genre" in normalized_filter and not any(
            genre.strip().lower() == normalized_filter["genre"]
            for genre in (movie.get("genres") or [])
        ):
            continue
        if "certification" in normalized_filter and (
            movie.get("certification") or ""
        ).strip().lower() != normalized_filter["certification"]:
            continue

        if not full_details:
            movies.append(
                {
                    "title": movie.get("title"),
                    "year": movie.get("year"),
                    "monitored": movie.get("monitored"),
                    "has_file": movie.get("hasFile"),
                }
            )
            continue

        movie_file = movie.get("movieFile", {})
        movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "monitored": movie.get("monitored"),
                "status": movie.get("status"),
                "has_file": movie.get("hasFile"),
                "file_path": movie_file.get("path") if movie.get("hasFile") else None,
                "file_size_mb": round(movie_file.get("size", 0) / (1024 * 1024), 1)
                if movie.get("hasFile")
                else None,
                "quality": movie_file.get("quality", {}).get("quality", {}).get("name")
                if movie.get("hasFile")
                else None,
                "genres": movie.get("genres", []),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "certification": movie.get("certification"),
                "tmdb_id": movie.get("tmdbId"),
                "imdb_id": movie.get("imdbId"),
            }
        )

    movies.sort(key=lambda item: item["title"] or "")
    return to_tsv(movies)


@log_tool_call
def get_radarr_quality_profiles() -> str:
    """List Radarr quality profiles as TSV; errors as strings."""
    radarr_config = get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/qualityprofile"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch quality profiles from Radarr: {exc}"

    quality_profiles_data = response.json()
    quality_profiles: list[dict] = []
    for profile in quality_profiles_data:
        quality_profiles.append(
            {
                "id": profile.get("id"),
                "name": profile.get("name"),
                "cutoff": profile.get("cutoff"),
                "language": profile.get("language"),
                "upgrade_allowed": profile.get("upgradeAllowed"),
            }
        )

    quality_profiles.sort(key=lambda profile: profile["name"] or "")
    return to_tsv(quality_profiles)


@log_tool_call
def get_radarr_root_folders() -> str:
    """List Radarr root folders as TSV; errors as strings."""
    radarr_config = get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/rootfolder"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch root folders from Radarr: {exc}"

    root_folders_data = response.json()
    root_folders: list[dict] = []
    for folder in root_folders_data:
        root_folders.append(
            {
                "id": folder.get("id"),
                "path": folder.get("path"),
                "free_space_gb": round(folder.get("freeSpace", 0) / (1024 * 1024 * 1024), 2),
                "accessible": folder.get("accessible"),
                "default": folder.get("default"),
            }
        )

    root_folders.sort(key=lambda folder: folder["path"] or "")
    return to_tsv(root_folders)


@log_tool_call
def add_radarr_movie(movie_query: str, root_folder_path: str, quality_profile_id: int) -> str:
    """Find and add a movie to Radarr with the selected root folder/profile; errors as strings."""
    if not movie_query or not movie_query.strip():
        return "Error: movie_query must not be empty"
    if not root_folder_path or not root_folder_path.strip():
        return "Error: root_folder_path must not be empty"

    radarr_config = get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    lookup_endpoint = f"{radarr_url}/api/v3/movie/lookup"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        lookup_response = requests.get(
            lookup_endpoint,
            params={"term": movie_query.strip()},
            headers=headers,
            timeout=20,
        )
        lookup_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to look up movie in Radarr: {exc}"

    lookup_results = lookup_response.json()
    if not lookup_results:
        return f"Error: No Radarr movie match found for '{movie_query}'"

    selected_movie = None
    normalized_query = movie_query.strip().lower()
    for candidate in lookup_results:
        candidate_title = str(candidate.get("title", "")).strip().lower()
        candidate_title_slug = str(candidate.get("titleSlug", "")).strip().lower()
        if normalized_query == candidate_title or normalized_query == candidate_title_slug:
            selected_movie = candidate
            break

    if selected_movie is None:
        selected_movie = lookup_results[0]

    movie_payload = dict(selected_movie)
    movie_payload["monitored"] = True
    movie_payload["monitorNewItems"] = "movieOnly"
    movie_payload["minimumAvailability"] = "released"
    movie_payload["rootFolderPath"] = root_folder_path
    movie_payload["qualityProfileId"] = quality_profile_id
    movie_payload["addOptions"] = {"searchForMovie": True}

    try:
        add_response = requests.post(
            f"{radarr_url}/api/v3/movie",
            json=movie_payload,
            headers=headers,
            timeout=20,
        )
        add_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to add movie to Radarr: {exc}"

    added_movie = add_response.json() if add_response.content else movie_payload
    added_title = added_movie.get("title") or movie_payload.get("title") or movie_query.strip()
    added_path = added_movie.get("path") or root_folder_path
    return f"Added Radarr movie '{added_title}' at '{added_path}' with quality profile {quality_profile_id}"


@log_tool_call
def delete_radarr_movie(movie_query: str, delete_files: bool = True) -> str:
    """Remove a movie from Radarr and exclude it from import lists.
    `delete_files` (default true) also removes media files. Errors as strings.
    """
    if not movie_query or not movie_query.strip():
        return "Error: movie_query must not be empty"

    radarr_config = get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    lookup_endpoint = f"{radarr_url}/api/v3/movie/lookup"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        lookup_response = requests.get(
            lookup_endpoint,
            params={"term": movie_query.strip()},
            headers=headers,
            timeout=20,
        )
        lookup_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to look up movie in Radarr: {exc}"

    lookup_results = lookup_response.json()
    if not lookup_results:
        return f"Error: No Radarr movie match found for '{movie_query}'"

    selected_movie = None
    normalized_query = movie_query.strip().lower()
    for candidate in lookup_results:
        candidate_title = str(candidate.get("title", "")).strip().lower()
        candidate_title_slug = str(candidate.get("titleSlug", "")).strip().lower()
        if normalized_query == candidate_title or normalized_query == candidate_title_slug:
            selected_movie = candidate
            break

    if selected_movie is None:
        selected_movie = lookup_results[0]

    movie_id = selected_movie.get("id")
    movie_title = selected_movie.get("title") or movie_query.strip()
    if movie_id is None:
        return f"Error: Radarr lookup for '{movie_title}' did not include a movie id"

    delete_endpoint = f"{radarr_url}/api/v3/movie/{movie_id}"

    try:
        response = requests.delete(
            delete_endpoint,
            params={"deleteFiles": str(delete_files).lower(), "addImportExclusion": "true"},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to delete movie from Radarr: {exc}"

    return f"Deleted Radarr movie '{movie_title}' (delete_files={delete_files})"


@log_tool_call
def get_radarr_current_downloads() -> str:
    """List current Radarr downloads and progress as TSV; errors as strings."""
    radarr_config = get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/queue"
    headers = {"X-Api-Key": radarr_api_key}
    params = {
        "page": 1,
        "pageSize": 1000,
        "sortKey": "title",
        "sortDirection": "ascending",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch current downloads from Radarr: {exc}"

    queue_data = response.json()
    queue_items = queue_data.get("records", queue_data) if isinstance(queue_data, dict) else queue_data

    downloads: list[dict] = []
    for item in queue_items:
        if str(item.get("status", "")).lower() != "downloading":
            continue

        size = item.get("size")
        size_left = item.get("sizeLeft")
        progress = None
        if isinstance(size, (int, float)) and size > 0 and isinstance(size_left, (int, float)):
            progress = round(((size - size_left) / size) * 100, 1)

        downloads.append(
            {
                "title": item.get("title"),
                "status": item.get("status"),
                "protocol": item.get("protocol"),
                "progress_percent": progress,
                "size_left_bytes": size_left,
                "time_left": item.get("timeleft"),
                "estimated_completion_time": item.get("estimatedCompletionTime"),
                "download_id": item.get("downloadId"),
            }
        )

    downloads.sort(key=lambda download: download["title"] or "")
    return to_tsv(downloads)

import requests

from media_stack.config import get_sonarr_config
from media_stack.formatting import to_tsv


def get_sonarr_shows(full_details: bool = False, title: str | None = None) -> str:
    """List Sonarr series as TSV; `full_details` adds metadata. Optional `title`
    matches case-insensitive partial titles (trimmed; blank is invalid). Empty
    matches return `Empty list`; failures return an error string.
    """
    if title is not None and not title.strip():
        return "Error: title must not be empty"
    normalized_title = title.strip().lower() if title is not None else None

    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/series"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch series from Sonarr: {exc}"

    series_data = response.json()
    series_rows: list[dict] = []
    for series in series_data:
        if normalized_title is not None and normalized_title not in (
            series.get("title") or ""
        ).lower():
            continue

        statistics = series.get("statistics", {})
        if not full_details:
            series_rows.append(
                {
                    "title": series.get("title"),
                    "year": series.get("year"),
                    "monitored": series.get("monitored"),
                    "episode_file_count": statistics.get("episodeFileCount"),
                }
            )
            continue

        series_rows.append(
            {
                "title": series.get("title"),
                "year": series.get("year"),
                "monitored": series.get("monitored"),
                "status": series.get("status"),
                "path": series.get("path"),
                "season_count": len(series.get("seasons", [])),
                "episode_file_count": statistics.get("episodeFileCount"),
                "total_episode_count": statistics.get("totalEpisodeCount"),
                "size_on_disk_gb": round(statistics.get("sizeOnDisk", 0) / (1024 * 1024 * 1024), 2)
                if statistics.get("sizeOnDisk")
                else None,
                "genres": series.get("genres", []),
                "runtime": str(series.get("runtime")) + " min" if series.get("runtime") else None,
                "network": series.get("network"),
                "certification": series.get("certification"),
                "language": series.get("originalLanguage", {}).get("name"),
                "tvdb_id": series.get("tvdbId"),
                "imdb_id": series.get("imdbId"),
            }
        )

    series_rows.sort(key=lambda item: item["title"] or "")
    return to_tsv(series_rows)


def get_sonarr_quality_profiles() -> str:
    """List Sonarr quality profiles as TSV; errors as strings."""
    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/qualityprofile"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch quality profiles from Sonarr: {exc}"

    quality_profiles_data = response.json()
    quality_profiles: list[dict] = []
    for profile in quality_profiles_data:
        quality_profiles.append(
            {
                "id": profile.get("id"),
                "name": profile.get("name"),
                "upgrade_allowed": profile.get("upgradeAllowed"),
                "min_format_score": profile.get("minFormatScore"),
                "cutoff_format_score": profile.get("cutoffFormatScore"),
            }
        )

    quality_profiles.sort(key=lambda profile: profile["name"] or "")
    return to_tsv(quality_profiles)


def get_sonarr_root_folders() -> str:
    """List Sonarr root folders as TSV; errors as strings."""
    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/rootfolder"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch root folders from Sonarr: {exc}"

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


def add_sonarr_show(
    show_query: str,
    root_folder_path: str,
    quality_profile_id: int,
    season_number_to_monitor: int,
) -> str:
    """Add a Sonarr series and monitor only `season_number_to_monitor`; errors as strings."""
    if not show_query or not show_query.strip():
        return "Error: show_query must not be empty"
    if not root_folder_path or not root_folder_path.strip():
        return "Error: root_folder_path must not be empty"
    if season_number_to_monitor < 0:
        return "Error: season_number_to_monitor must be greater than or equal to 0"

    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    lookup_endpoint = f"{sonarr_url}/api/v3/series/lookup"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        lookup_response = requests.get(
            lookup_endpoint,
            params={"term": show_query.strip()},
            headers=headers,
            timeout=20,
        )
        lookup_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to look up series in Sonarr: {exc}"

    lookup_results = lookup_response.json()
    if not lookup_results:
        return f"Error: No Sonarr series match found for '{show_query}'"

    selected_series = None
    normalized_query = show_query.strip().lower()
    for candidate in lookup_results:
        candidate_title = str(candidate.get("title", "")).strip().lower()
        candidate_title_slug = str(candidate.get("titleSlug", "")).strip().lower()
        if normalized_query == candidate_title or normalized_query == candidate_title_slug:
            selected_series = candidate
            break

    if selected_series is None:
        selected_series = lookup_results[0]

    seasons = selected_series.get("seasons", [])
    season_numbers = {season.get("seasonNumber") for season in seasons}
    if season_number_to_monitor not in season_numbers:
        return (
            "Error: season_number_to_monitor "
            f"{season_number_to_monitor} is not available for '{selected_series.get('title') or show_query.strip()}'"
        )

    series_payload = dict(selected_series)
    series_payload["monitored"] = True
    series_payload["rootFolderPath"] = root_folder_path
    series_payload["qualityProfileId"] = quality_profile_id
    series_payload["addOptions"] = {"searchForMissingEpisodes": True}

    # Keep monitoring limited to the requested season only.
    series_payload["seasons"] = [
        {
            **season,
            "monitored": season.get("seasonNumber") == season_number_to_monitor,
        }
        for season in seasons
    ]

    try:
        add_response = requests.post(
            f"{sonarr_url}/api/v3/series",
            json=series_payload,
            headers=headers,
            timeout=20,
        )
        add_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to add show to Sonarr: {exc}"

    added_series = add_response.json() if add_response.content else series_payload
    added_title = added_series.get("title") or series_payload.get("title") or show_query.strip()
    added_path = added_series.get("path") or root_folder_path
    return (
        f"Added Sonarr show '{added_title}' at '{added_path}' with quality profile {quality_profile_id}; "
        f"monitoring season {season_number_to_monitor} only"
    )


def delete_sonarr_show(show_query: str, delete_files: bool = True) -> str:
    """Remove a series from Sonarr; `delete_files` (default true) also removes media files. Errors as strings."""
    if not show_query or not show_query.strip():
        return "Error: show_query must not be empty"

    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    lookup_endpoint = f"{sonarr_url}/api/v3/series/lookup"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        lookup_response = requests.get(
            lookup_endpoint,
            params={"term": show_query.strip()},
            headers=headers,
            timeout=20,
        )
        lookup_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to look up series in Sonarr: {exc}"

    lookup_results = lookup_response.json()
    if not lookup_results:
        return f"Error: No Sonarr series match found for '{show_query}'"

    selected_series = None
    normalized_query = show_query.strip().lower()
    for candidate in lookup_results:
        candidate_title = str(candidate.get("title", "")).strip().lower()
        candidate_title_slug = str(candidate.get("titleSlug", "")).strip().lower()
        if normalized_query == candidate_title or normalized_query == candidate_title_slug:
            selected_series = candidate
            break

    if selected_series is None:
        selected_series = lookup_results[0]

    series_id = selected_series.get("id")
    series_title = selected_series.get("title") or show_query.strip()
    if series_id is None:
        return f"Error: Sonarr lookup for '{series_title}' did not include a series id"

    delete_endpoint = f"{sonarr_url}/api/v3/series/{series_id}"

    try:
        response = requests.delete(
            delete_endpoint,
            params={"deleteFiles": str(delete_files).lower()},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to delete show from Sonarr: {exc}"

    return f"Deleted Sonarr show '{series_title}' (delete_files={delete_files})"


def get_sonarr_current_downloads() -> str:
    """List current Sonarr downloads and progress as TSV; errors as strings."""
    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/queue"
    headers = {"X-Api-Key": sonarr_api_key}
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
        return f"Error: Failed to fetch current downloads from Sonarr: {exc}"

    queue_data = response.json()
    queue_items = queue_data.get("records", queue_data) if isinstance(queue_data, dict) else queue_data

    downloads: list[dict] = []
    for item in queue_items:
        if str(item.get("status", "")).lower() != "downloading" and str(item.get("status", "")).lower() != "queued":
            continue

        size = item.get("size")
        size_left = item.get("sizeleft")
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
                "series_id": item.get("seriesId"),
                "episode_id": item.get("episodeId"),
            }
        )

    downloads.sort(key=lambda download: download["title"] or "")
    return to_tsv(downloads)

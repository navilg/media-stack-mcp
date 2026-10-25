def normalize_library_filter(filter: object) -> dict[str, bool | str] | str:
    """Validate and normalize the optional Radarr/Sonarr library filter."""
    normalized_filter: dict[str, bool | str] = {}
    if filter is None:
        return normalized_filter
    if not isinstance(filter, dict):
        return "Error: filter must be a JSON object"
    for key, value in filter.items():
        if key not in ("monitored", "has_file", "genre", "certification"):
            return f"Error: unsupported filter key: {key}"
        if key in ("monitored", "has_file"):
            if not isinstance(value, bool):
                return f"Error: filter.{key} must be a boolean"
            normalized_filter[key] = value
        else:
            if not isinstance(value, str) or not value.strip():
                return f"Error: filter.{key} must be a non-empty string"
            normalized_filter[key] = value.strip().lower()
    return normalized_filter

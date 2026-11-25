from collections.abc import Callable

import requests

from media_stack.formatting import to_tsv


def get_history(
    event_type: str,
    sort_direction: str,
    limit: int,
    event_types: dict[str, int],
    service: str,
    get_config: Callable[[], tuple[str, str] | str],
    includes: dict[str, str],
    format_record: Callable[[dict], dict],
) -> str:
    if not isinstance(event_type, str) or event_type.strip().lower() not in (
        *event_types, "all"
    ):
        return f"Error: unsupported {service} history event_type"
    if not isinstance(sort_direction, str) or sort_direction.strip().lower() not in (
        "ascending", "descending"
    ):
        return "Error: sort_direction must be ascending or descending"
    if type(limit) is not int or limit < 1:
        return "Error: limit must be a positive integer"

    config = get_config()
    if isinstance(config, str):
        return config

    url, api_key = config
    params = {
        "page": 1,
        "pageSize": min(limit, 1000),
        "sortKey": "date",
        "sortDirection": sort_direction.strip().lower(),
        **includes,
    }
    normalized_type = event_type.strip().lower()
    if normalized_type != "all":
        params["eventType"] = event_types[normalized_type]

    rows: list[dict] = []
    try:
        while True:
            response = requests.get(
                f"{url}/api/v3/history",
                params=params,
                headers={"X-Api-Key": api_key},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            records = payload["records"]
            total = payload["totalRecords"]
            if (
                not isinstance(records, list)
                or type(total) is not int
                or total < 0
                or (not records and len(rows) < total)
            ):
                return f"Error: Invalid history response from {service}"
            rows.extend(format_record(record) for record in records)
            if len(rows) >= total or len(rows) >= limit:
                break
            params["page"] += 1
    except requests.RequestException as exc:
        return f"Error: Failed to fetch history from {service}: {exc}"
    except (KeyError, TypeError, ValueError, AttributeError):
        return f"Error: Invalid history response from {service}"

    return to_tsv(rows[:limit])

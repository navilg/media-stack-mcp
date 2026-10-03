import argparse
import os

from media_stack.constants import VALID_TOOLSETS


def get_floppy_config() -> tuple[str, str] | str:
    floppy_url = os.getenv("FLOPPY_URL")
    floppy_api_key = os.getenv("FLOPPY_API_KEY")

    if not floppy_url:
        return "Error: FLOPPY_URL is not set"
    if not floppy_api_key:
        return "Error: FLOPPY_API_KEY is not set"

    return floppy_url.rstrip("/"), floppy_api_key


def get_radarr_config() -> tuple[str, str] | str:
    radarr_url = os.getenv("RADARR_URL")
    radarr_api_key = os.getenv("RADARR_API_KEY")

    if not radarr_url:
        return "Error: RADARR_URL is not set"
    if not radarr_api_key:
        return "Error: RADARR_API_KEY is not set"

    return radarr_url.rstrip("/"), radarr_api_key


def get_sonarr_config() -> tuple[str, str] | str:
    sonarr_url = os.getenv("SONARR_URL")
    sonarr_api_key = os.getenv("SONARR_API_KEY")

    if not sonarr_url:
        return "Error: SONARR_URL is not set"
    if not sonarr_api_key:
        return "Error: SONARR_API_KEY is not set"

    return sonarr_url.rstrip("/"), sonarr_api_key


def parse_toolsets(value: str) -> str:
    """Validate comma-separated toolset names."""
    if not value:
        return value

    for item in value.split(","):
        toolset = item.strip()
        if toolset and toolset not in VALID_TOOLSETS:
            raise argparse.ArgumentTypeError(
                f"invalid toolset: '{toolset}'. Valid options: {', '.join(sorted(VALID_TOOLSETS))}"
            )

    return value


def compute_tags_to_disable(disable_toolsets_arg: str) -> set[str]:
    """Compute disabled tags for mcp.disable()."""
    tags_to_disable = {"deprecated"}
    if disable_toolsets_arg:
        for tag in disable_toolsets_arg.split(","):
            normalized = tag.strip()
            if normalized:
                tags_to_disable.add(normalized)
    return tags_to_disable

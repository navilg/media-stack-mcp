# MCP Media Stack

FastMCP server that exposes media tools backed by Trakt, Floppy, Radarr, and Sonarr.

## Tools

The server currently exposes these MCP tools:

- `check_trakt_profile_privacy(username=None)`
- `get_trakt_public_watched_movies(username=None, days=30)`
- `get_trakt_public_watched_shows(username=None, days=30)`
- `get_trakt_public_liked_movies(username=None, threshold_user_rating=7, limit=50)`
- `get_trakt_public_disliked_movies(username=None, threshold_user_rating=6, limit=50)`
- `get_trakt_latest_high_rated_movies(days=30, threshold_rating=7, limit=50)`
- `get_floppy_latest_high_rated_movies(days=30, threshold_rating=7, limit=50)`
- `get_trakt_popular_movies(limit=50)`
- `get_radarr_movies()`
- `get_radarr_quality_profiles()`
- `get_radarr_root_folders()`
- `add_radarr_movie(movie_query, root_folder_path, quality_profile_id)`
- `delete_radarr_movie(movie_query, delete_files=False)`
- `get_radarr_current_downloads()`
- `get_sonarr_shows()`
- `get_sonarr_quality_profiles()`
- `get_sonarr_root_folders()`
- `add_sonarr_show(show_query, root_folder_path, quality_profile_id, season_number_to_monitor)`
- `delete_sonarr_show(show_query, delete_files=False)`
- `get_sonarr_current_downloads()`
- `search_trakt_movie_by_title(title, year=None, limit=5)`
- `search_trakt_show_by_title(title, year=None, limit=5)`

## Prerequisites

- Python 3.11+ (for local run) or Docker (for container run)
- Trakt API client ID

## Environment variables

Set the following as needed:

- `TRAKT_CLIENT_ID` (required)
- `TRAKT_USERNAME` (optional default username if `username` tool argument is omitted)
- `RADARR_URL` (required for Radarr tools)
- `RADARR_API_KEY` (required for Radarr tools)
- `SONARR_URL` (required for Sonarr tools)
- `SONARR_API_KEY` (required for Sonarr tools)
- `FLOPPY_URL` (Floppy instance base URL, required for Floppy tools)
- `FLOPPY_API_KEY` (required for Floppy tools; needs `watchlist:read` scope)
- `DISABLE_TOOLSETS` (optional comma-separated list of toolsets to disable at startup, e.g. `radarr,trakt`)

## Quick start (Docker)

Build image:

```bash
docker build -t mcp-media-stack:latest .
```

Run container (port 8000):

```bash
docker run --rm -p 8000:8000 \
  -e TRAKT_CLIENT_ID=your_trakt_client_id \
  -e TRAKT_USERNAME=your_trakt_username \
  -e DISABLE_TOOLSETS=radarr \
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Quick start (.env file)

Create `.env`:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_USERNAME=your_trakt_username
DISABLE_TOOLSETS=radarr
```

Run with env file:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Local run (without Docker)

```bash
python -m pip install -r requirements.txt
python server.py --host 0.0.0.0 --port 8000 --transport streamable-http
```

## Disabling tool groups

You can disable entire groups of related tools at startup using the `DISABLE_TOOLSETS` environment variable. This is useful when you only want to expose Trakt tools or Radarr tools, not both.

Available toolset names:

- `floppy`: Recently completed movies with high personal ratings
- `trakt`: All Trakt tools (profile, watched, liked, disliked, latest, popular, trending)
- `radarr`: All Radarr tools (list, quality, root folders, add, delete, downloads)
- `sonarr`: Sonarr tools (`get_sonarr_shows`, `get_sonarr_quality_profiles`, `get_sonarr_root_folders`, `add_sonarr_show`, `delete_sonarr_show`, `get_sonarr_current_downloads`)

Examples:

```bash
# Default: all tools enabled (only 'deprecated' tag is disabled)
python server.py

# Disable all Trakt tools (only Radarr tools are available)
DISABLE_TOOLSETS=trakt python server.py

# Disable all Radarr tools (only Trakt tools are available)
DISABLE_TOOLSETS=radarr python server.py

# Disable both (no tools available — mostly useful for testing)
DISABLE_TOOLSETS=radarr,trakt python server.py
```

Passing an invalid toolset name produces an error at startup:

```bash
DISABLE_TOOLSETS=invalid_name python server.py
# error: invalid toolset: 'invalid_name'. Valid options: floppy, radarr, sonarr, trakt
```

> **Note:** The `deprecated` tag is always disabled internally and reserved for future use.

## Test script

A test script is included to validate tool functionality against the Python functions in `server.py`.

- Create your test env file:

```bash
cp test.env.example test.env
```

- Fill in credentials and test inputs in `test.env`.

- Run tests (requires `pytest`):

```bash
# Run all tests
python -m pytest test_server.py -v

# Or run directly
python test_server.py
```

The script automatically loads `test.env` and runs all test functions sequentially, printing results for each tool call.

## Operational commands

View logs:

```bash
docker logs -f mcp-media-stack
```

List running containers:

```bash
docker ps
```

Stop container:

```bash
docker stop mcp-media-stack
```

## Notes

- Default server bind is `0.0.0.0:8000`.
- Trakt tools support passing `username` directly or using `TRAKT_USERNAME` as fallback.
- `get_trakt_public_watched_movies` defaults to the last 30 days.
- `get_floppy_latest_high_rated_movies` returns tracked movies completed in the last `days` calendar-date window with a personal score at least `threshold_rating` (0-10), newest completion first. Unlike Trakt's tool, it does not query recently released movies or use provider ratings. It paginates before applying the score threshold and returns up to `limit` TSV rows, or `Empty list`. The Floppy integration test skips when its credentials are absent.
- Trakt tools return condensed movie metadata including title, release date, ratings, genres, and certification.
- `add_radarr_movie` looks up the movie by query string, then adds it with monitor set to movie only, minimum availability set to released, and search enabled.
- `delete_radarr_movie` looks up the movie by query string before deleting it; set `delete_files=True` to remove the file from disk as well.
- `get_radarr_current_downloads` reports queue items whose status is `downloading`, including progress percent and time-left fields when Radarr provides them.
- `add_sonarr_show` adds a series and monitors only the requested season, not all seasons.
- `delete_sonarr_show` looks up a series by query string before deleting it; set `delete_files=True` to remove files from disk as well.
- `get_sonarr_current_downloads` reports queue items whose status is `downloading`, including progress percent and time-left fields when Sonarr provides them.

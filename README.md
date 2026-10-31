# MCP Media Stack

FastMCP server that exposes media tools backed by Trakt, Floppy, TMDB, Radarr, and Sonarr.

## Tools

The server currently exposes these MCP tools:

- `check_trakt_profile_privacy(username=None)`
- `get_trakt_public_watched_movies(username=None, days=30)`
- `get_trakt_public_watched_shows(username=None, days=30)`
- `get_trakt_public_liked_movies(username=None, threshold_user_rating=7, limit=50)`
- `get_trakt_public_liked_shows(username=None, threshold_user_rating=7, limit=50)`
- `get_trakt_public_disliked_movies(username=None, threshold_user_rating=6, limit=50)`
- `get_trakt_latest_high_rated_movies(days=30, threshold_rating=7, limit=50)`
- `get_trakt_latest_high_rated_shows(days=30, threshold_rating=7, limit=50)`
- `get_trakt_popular_movies(limit=50)`
- `get_trakt_popular_shows(limit=50)`
- `get_trakt_trending_movies(limit=50)`
- `get_trakt_trending_shows(limit=50)`
- `search_trakt_movie_by_title(title, year=None, limit=5)`
- `search_trakt_show_by_title(title, year=None, limit=5)`
- `get_tmdb_latest_high_rated_movies(days=30, threshold_rating=7, limit=50)`
- `get_tmdb_latest_high_rated_shows(days=30, threshold_rating=7, limit=50)`
- `get_tmdb_trending_movies(limit=50, time_window=week)`
- `get_tmdb_trending_shows(limit=50, time_window=week)`
- `get_floppy_watched_movies(days=30, limit=200)`
- `get_floppy_watched_tv_seasons(days=30, limit=200)`
- `get_floppy_liked_movies(threshold_user_rating=7, days=30, limit=50)`
- `get_floppy_liked_tv_seasons(threshold_user_rating=8, days=30, limit=50)`
- `get_floppy_disliked_movies(threshold_user_rating=6, days=30, limit=50)`
- `get_floppy_disliked_tv_seasons(threshold_user_rating=7, days=30, limit=50)`
- `get_floppy_trending_movies()`
- `search_floppy_movie_by_title(title, limit=5)`
- `search_floppy_tv_show_by_title(title, limit=5)`

`get_tmdb_latest_high_rated_movies()` and `get_tmdb_latest_high_rated_shows()` 
fetch recent high-rated content from TMDB with automatic retry logic (10 attempts 
with exponential backoff) to handle intermittent API failures. Both tools filter 
by release date, minimum vote average (≥7), and vote count (≥50), sorted by 
popularity. Pagination loops until the limit is reached or all pages are exhausted.

`get_tmdb_latest_high_rated_shows()` filters TV shows by their latest season 
premiere date, requiring an extra API call per show to determine the most recent 
season's air date. This is useful for discovering shows with recent season releases.

`get_tmdb_trending_movies()` fetches trending movies from TMDB for the specified 
time window (day or week). It includes automatic retry logic (10 attempts with 
exponential backoff) and pagination until the limit is reached or all pages are 
exhausted.

`get_tmdb_trending_shows()` fetches trending TV shows from TMDB for the specified 
time window (day or week), including the latest season air date. It includes 
automatic retry logic (10 attempts with exponential backoff) and pagination until 
the limit is reached or all pages are exhausted.

Output is TSV format. Movies output: `title`, `release_date`, `average_rating`, 
`vote_count`, `popularity`, `genre_ids`, `original_language`, `overview`, `tmdb_id`. 
TV output: `name`, `latest_air_date`, `average_rating`, `vote_count`, `popularity`, 
`genre_ids`, `original_language`, `overview`, `tmdb_id`.

- `get_radarr_movies(full_details=False, title=None, filter=None)`
- `get_radarr_quality_profiles()`
- `get_radarr_root_folders()`
- `add_radarr_movie(movie_query, root_folder_path, quality_profile_id)`
- `delete_radarr_movie(movie_query, delete_files=True)`
- `get_radarr_current_downloads()`
- `get_sonarr_shows(full_details=False, title=None, filter=None)`
- `get_sonarr_quality_profiles()`
- `get_sonarr_root_folders()`
- `add_sonarr_show(show_query, root_folder_path, quality_profile_id, season_number_to_monitor)`
- `delete_sonarr_show(show_query, delete_files=True)`
- `get_sonarr_current_downloads()`

`get_radarr_movies()` returns short TSV rows containing only `title`, `year`,
`monitored`, and `has_file`. Pass `full_details=True` to include all existing
metadata: status, file path, file size, quality, genres, runtime, certification,
TMDb ID, and IMDb ID.
Optionally pass `title="Dune"` to return case-insensitive partial title matches
(for example, `Dune` and `Dune: Part Two`), ignoring surrounding whitespace in the
filter. Omit `title` to return the entire library. An empty or
whitespace-only title returns an error; no matches returns `Empty list`.

Optionally pass a JSON/dict object as `filter`, for example:

```json
{"monitored": true, "has_file": true, "genre": "romance", "certification": "R"}
```

Only these four keys are allowed, and each is optional. `monitored` and `has_file`
must be booleans; `genre` and `certification` must be non-empty strings.
All supplied fields must match (AND), together with any `title` filter.
Genre matches one complete genre in the movie's genres; certification matches
the complete rating. Both ignore case and surrounding whitespace.
Omitting `filter`, passing `null`/`None`, or passing `{}` leaves the library
unfiltered apart from any `title` filter. Invalid keys or values return an error.
Filtering works with both short and full output; no matches returns `Empty list`.

`get_sonarr_shows()` returns short TSV rows containing only `title`, `year`,
`monitored`, and `episode_file_count`. Pass `full_details=True` to return all
previous series metadata, including status, path, season and episode counts,
disk usage, genres, runtime, network, certification, language, TVDb ID, and IMDb ID.
Optionally pass `title="dark"` for case-insensitive partial title matching,
ignoring surrounding whitespace in the filter. Omit `title` to return all shows.
An empty or whitespace-only title returns an error; no matches returns `Empty list`.

Sonarr also accepts the same optional JSON/dict `filter` with only `monitored`,
`has_file`, `genre`, and `certification`, for example:

```json
{"monitored": true, "has_file": true, "genre": "drama", "certification": "TV-MA"}
```

Each key is optional. Boolean and string validation, AND matching with `title`,
case-insensitive exact genre/certification matching, and empty-filter behavior
are the same as Radarr. For shows, `has_file=true` means at least one downloaded
episode (`episodeFileCount > 0`); `false` matches shows with no downloaded
episodes, including missing or null counts. The existing output columns remain
unchanged in both short and full formats.

## Prerequisites

- Python 3.11+ (for local run) or Docker (for container run)
- Trakt API client ID

## Environment variables

Set the following as needed:

- `TRAKT_CLIENT_ID` (required for Trakt tools)
- `TRAKT_USERNAME` (optional default username if `username` tool argument is omitted)
- `TMDB_API_KEY` (required for TMDB tools; use Bearer token format)
- `RADARR_URL` (required for Radarr tools)
- `RADARR_API_KEY` (required for Radarr tools)
- `SONARR_URL` (required for Sonarr tools)
- `SONARR_API_KEY` (required for Sonarr tools)
- `FLOPPY_URL` (Floppy instance base URL, required for Floppy tools)
- `FLOPPY_API_KEY` (required for Floppy tools; needs `watchlist:read` scope)
- `DISABLE_TOOLSETS` (optional comma-separated list of toolsets to disable at startup, e.g. `radarr,tmdb,trakt`)

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
  -e TMDB_API_KEY=your_tmdb_api_token \
  -e DISABLE_TOOLSETS=radarr \
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Publishing Docker images

The GitHub Actions workflow publishes two Docker Hub images whenever a Git tag
is pushed:

- `<image>:aarch64-<tag>` for `linux/arm64`
- `<image>:amd64-<tag>` for `linux/amd64`

Configure these repository secrets under **Settings > Secrets and variables >
Actions**:

- `DOCKERHUB_USERNAME`: Docker Hub login username.
- `DOCKERHUB_TOKEN`: Docker Hub access token with write permission for the image
  repository.

By default, `<image>` is `<DOCKERHUB_USERNAME>/media-stack-mcp`. To publish to a
different repository or organization, set the repository variable
`DOCKERHUB_IMAGE` to the full Docker Hub image name (for example,
`my-org/media-stack-mcp`, without a tag). The Docker Hub account must have write
access to that repository.

For example, pushing the Git tag `v1.0.0` publishes
`<image>:aarch64-v1.0.0` and `<image>:amd64-v1.0.0`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Git tags must produce valid Docker image tags when prefixed with `aarch64-` or
`amd64-` (use letters, digits, dots, underscores, and hyphens, with at most 120
characters in the Git tag).

## Quick start (.env file)

Create `.env`:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_USERNAME=your_trakt_username
TMDB_API_KEY=your_tmdb_api_token
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

## SSE mode

The default transport is Streamable HTTP, with the MCP endpoint at `http://localhost:8000/mcp`.
To use SSE instead:

```bash
python server.py --host 0.0.0.0 --port 8000 --transport sse
```

Configure your MCP client to use SSE with the URL `http://localhost:8000/sse`.

For Docker, override the default command:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --name mcp-media-stack \
  mcp-media-stack:latest python server.py --transport sse
```

## Disabling tool groups

You can disable entire groups of related tools at startup using the `DISABLE_TOOLSETS` environment variable. This is useful when you only want to expose Trakt tools or Radarr tools, not both.

Available toolset names:

- `floppy`: All Floppy tools (`get_floppy_watched_movies`, `get_floppy_watched_tv_seasons`, `get_floppy_liked_movies`, `get_floppy_liked_tv_seasons`, `get_floppy_disliked_movies`, `get_floppy_disliked_tv_seasons`, `get_floppy_trending_movies`, `search_floppy_movie_by_title`, `search_floppy_tv_show_by_title`)
- `trakt`: All Trakt tools (profile, watched, liked, disliked, latest high-rated, popular, trending, search)
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

## Test scripts

Two test scripts are included:

- `test_server.py`: integration and CLI tests for server behavior and tool functions.
- `test_mcp_http.py`: Streamable HTTP MCP handshake and optional tool-call smoke test.

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

Run the HTTP smoke test against a running MCP server:

```bash
# List tools after initialize/initialized handshake
python test_mcp_http.py --url http://localhost:8000/mcp

# Call a specific tool with JSON arguments
python test_mcp_http.py \
  --url http://localhost:8000/mcp \
  --tool get_floppy_watched_movies \
  --arguments '{"days": 7, "limit": 5}'
```

`test_server.py` automatically loads `test.env` and runs test functions sequentially.

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
- `get_floppy_watched_movies` reads the authenticated user's movie history for the last `days` dates, returning completed entries only, newest first, up to `limit` (maximum 200). Repeat plays are represented by Floppy's `play_count`. The history endpoint requires a Floppy API key with watchlist read access.
- `get_floppy_watched_tv_seasons` reads all pages of TV episode history (`media_type=tv`) in the requested date window and groups completed episodes by provider show ID and season. It returns TSV columns `title`, `season_number`, `watched_episode_count`, `total_episode_count`, and `latest_watched_at`, newest first. Rewatched episodes count once per season; watched counts refer only to the date window, not lifetime progress or full-season completion. Season details (`/api/v1/media/tv/{source}/{media_id}/{season_number}/`) supply the total count via `max_progress`. `limit` caps season rows (1-200), not fetched history entries. Both endpoints require watchlist read access. No matching episodes returns `Empty list`; request failures or invalid history/season details return an `Error:` string.
- `get_floppy_liked_movies` and `get_floppy_liked_tv_seasons` read rated, completed movies/TV seasons in the requested date window and then filter using the `threshold_user_rating` argument before applying the final `limit`. Returns TSV with title, year, ratings (imdb_rating, provider_rating, user_rating), genres, completed_date, certification, language, and overview.
- `get_floppy_disliked_movies` and `get_floppy_disliked_tv_seasons` read rated, completed movies/TV seasons in the requested date window and then filter using the `threshold_user_rating` argument before applying the final `limit`. Returns TSV with the same fields as the liked variants.
- `get_floppy_trending_movies` returns up to 20 entries from Floppy discover data (`trending_right_now`) and enriches each result with detailed metadata.
- `search_floppy_movie_by_title` uses Floppy search and then enriches each result with detailed metadata.
- `search_floppy_tv_show_by_title` uses Floppy search for TV shows and then enriches each result with detailed metadata. Returns TSV with title, year, status, rating, genres, certification, language, overview, and source.
- Trakt tools return condensed movie metadata including title, release date, ratings, genres, and certification.
- `add_radarr_movie` looks up the movie by query string, then adds it with monitor set to movie only, minimum availability set to released, and search enabled.
- `delete_radarr_movie` looks up the movie by query string before deleting it and always adds an import-list exclusion so lists cannot automatically add it back. Media files are deleted by default; set `delete_files=False` to keep them on disk.
- `get_radarr_current_downloads` reports queue items whose status is `downloading`, including progress percent and time-left fields when Radarr provides them.
- `add_sonarr_show` adds a series and monitors only the requested season, not all seasons.
- `delete_sonarr_show` looks up a series by query string before deleting it and always adds an import-list exclusion so lists cannot automatically add it back. Media files are deleted by default; set `delete_files=False` to keep them on disk.
- `get_sonarr_current_downloads` reports queue items whose status is `downloading`, including progress percent and time-left fields when Sonarr provides them.

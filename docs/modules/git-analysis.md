# Git Repository Analysis Tools

Tools for mining git commit history, analyzing contributor networks, and
correlating code changes with investigation events.

**Dependency:** `pydriller` (installed via `uv add pydriller`)

## analyze_git_repo.py

Clone, ingest, and query git repository commit history. Classifies commits
by subsystem with security sensitivity ratings.

### Clone a repository

```bash
uv run python tools/analyze_git_repo.py clone https://github.com/nginx/nginx.git --name nginx
```

Bare-clones the repo to `datasets/git_repos/<name>/` and registers it in
`git_analysis.db`.

### Ingest commits

```bash
uv run python tools/analyze_git_repo.py ingest --repo nginx
uv run python tools/analyze_git_repo.py ingest --repo nginx --append
```

Parses all commits via PyDriller. Extracts author, committer, date, timezone,
files changed, insertions/deletions. Classifies each file change into a
subsystem. Without `--append`, clears and re-ingests.

### List contributors

```bash
uv run python tools/analyze_git_repo.py contributors --repo nginx
uv run python tools/analyze_git_repo.py contributors --repo nginx --subsystem tls_ssl
uv run python tools/analyze_git_repo.py contributors --repo nginx --limit 20
```

Shows contributors ranked by commit count with primary timezone and subsystems.
Filter by subsystem to see who touches security-sensitive code.

### Commit timeline

```bash
uv run python tools/analyze_git_repo.py timeline --repo nginx --subsystem tls_ssl --start 2019-01 --end 2020-01
uv run python tools/analyze_git_repo.py timeline --repo nginx --author "dounin"
```

Monthly aggregation of commits, authors, insertions, deletions. Filter by
subsystem, author, and date range.

### Author activity

```bash
uv run python tools/analyze_git_repo.py activity --repo nginx --author "dounin"
```

Per-month breakdown of a specific author's commits with subsystem detail.

### Commit hotspots

```bash
uv run python tools/analyze_git_repo.py hotspots --repo nginx --start 2019-12-01 --end 2019-12-31
uv run python tools/analyze_git_repo.py hotspots --repo nginx --start 2019-03-01 --end 2019-04-01 --security-only
```

Day-by-day commit listing for a date range. Flags security-sensitive
subsystem touches. Use `--security-only` to filter to tls_ssl, auth, crypto,
connection subsystems.

### Subsystem authors

```bash
uv run python tools/analyze_git_repo.py subsystem-authors --repo nginx --subsystem tls_ssl
uv run python tools/analyze_git_repo.py subsystem-authors --repo nginx --subsystem auth
```

Ranked list of who has touched a specific subsystem, with first/last touch
dates, line counts, and timezone.

### Event correlation

```bash
uv run python tools/analyze_git_repo.py correlate --repo nginx --days 14
uv run python tools/analyze_git_repo.py correlate --repo nginx --days 30
```

Correlates commit activity with investigation event timeline. For each key
date, shows total commits, security-sensitive commits, and unique authors in
the +/- N day window. Uses active investigation profile to filter events.

### Repository stats

```bash
uv run python tools/analyze_git_repo.py stats --repo nginx
```

Overview: total commits, contributors, date range, subsystem distribution,
timezone distribution.

## git_contributor_network.py

Network analysis of contributor relationships, institutional clustering,
and influence metrics.

### Co-authorship network

```bash
uv run python tools/git_contributor_network.py coauthors --repo nginx
uv run python tools/git_contributor_network.py coauthors --repo nginx --min-shared 10
```

Pairs of contributors who edited the same files, ranked by shared file count.
Shows which subsystems they share.

### File overlap analysis

```bash
uv run python tools/git_contributor_network.py file-overlap --repo nginx --subsystem tls_ssl
```

Files edited by multiple contributors in a subsystem. Shows who has touched
each file — useful for identifying shared code ownership in security areas.

### Email domain analysis

```bash
uv run python tools/git_contributor_network.py domain-analysis --repo nginx
```

Groups contributors by email domain to reveal institutional clustering.
Shows per-domain commit counts, subsystem focus, and individual contributors.

### Influence metrics

```bash
uv run python tools/git_contributor_network.py influence --repo nginx
uv run python tools/git_contributor_network.py influence --repo nginx --limit 20
```

Composite influence score based on: total commits, subsystem breadth,
security-sensitive commit ratio, unique files touched, tenure. Identifies
who has the most control over the codebase.

### Contributor transitions

```bash
uv run python tools/git_contributor_network.py transitions --repo nginx
uv run python tools/git_contributor_network.py transitions --repo nginx --start 2019-01 --end 2023-01
```

Timeline of contributor onboarding and offboarding. Shows when each person
made their first and last commits. Filter by date range to focus on key periods.

## Subsystem Classification

Commits are classified by file path into subsystems with security ratings:

| Subsystem | Security Level | Path Patterns |
|-----------|---------------|---------------|
| `tls_ssl` | CRITICAL | `ngx_event_openssl*`, `ngx_http_ssl*`, `ngx_stream_ssl*` |
| `auth` | CRITICAL | `ngx_http_auth*` |
| `crypto` | CRITICAL | Anything touching RAND, entropy, PRNG |
| `connection` | HIGH | `ngx_event*`, `ngx_process*`, `ngx_socket*` |
| `http_core` | HIGH | `ngx_http_request*`, `ngx_http_header*`, `ngx_http_core*` |
| `logging` | MEDIUM | `ngx_log*`, `ngx_http_log*` |
| `modules` | MEDIUM | `src/http/modules/*` (general) |
| `stream` | MEDIUM | `src/stream/*` |
| `mail` | MEDIUM | `src/mail/*` |
| `core` | MEDIUM | `src/core/*`, `src/os/*` |
| `build` | LOW | `auto/*`, `configure`, `Makefile` |
| `docs` | LOW | `docs/*`, `CHANGES*` |
| `tests` | LOW | Test files |

## Database

Data stored in `git_analysis.db` (SQLite, WAL mode). Tables:
- `git_repos` — registered repositories
- `git_commits` — commit metadata (author, date, timezone, subsystems)
- `git_contributors` — contributor summaries
- `git_file_changes` — per-file change records with subsystem classification

All commands support `--output FILE` for JSON export and `--json` for stdout JSON.

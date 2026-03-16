# screamsheet
One page news, suitable for printout in the morning!

## Running the system

```bash
uv run screamsheet        # generate all sheets and send to printer
```

---

## DB Update — NHL Teams & Players Cache

The local SQLite cache (`src/screamsheet/db/nhl.db`) stores NHL team and player
reference data so that live lookups during generation are fast and resilient to
transient API failures.  The cache is populated / refreshed by `update_db.sh`.

### Manual run

```bash
# From any working directory:
bash /home/peter/Code/screamsheet/update_db.sh
```

Or use the `uv` entry point directly (no shell script):

```bash
cd /home/peter/Code/screamsheet
uv run db_update                                    # use default DB path
uv run db_update --db src/screamsheet/db/nhl.db    # explicit path
```

### Cron — weekly sync (every Monday at 3 am)

```cron
0 3 * * 1 /home/peter/Code/screamsheet/update_db.sh
```

Add with `crontab -e`.  Verify with `crontab -l`.

### Log output

Each run appends to a dated file:

```
logfiles/update_db_log_YYYYMMDD.txt
```

Messages are also echoed to stdout so cron mailers and systemd journal capture them.

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Both teams and players synced with non-zero row counts |
| `1`  | A sync raised an exception or returned zero rows (network failure) |

### `pyproject.toml` — entry point (no changes needed)

The `db_update` CLI command is already wired in `[project.scripts]`:

```toml
[project.scripts]
db_update = "screamsheet.db.db_update:main"
```

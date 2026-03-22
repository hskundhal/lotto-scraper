# CHECKPOINT.md — AI-Readable Project Context

> **Purpose**: This file is the authoritative reference for any AI agent (or human) resuming work on this project. It captures the full context: what was built, why, how it works, and what remains to be done.

---

## Project: Lotto Max OLG Scraper

**Goal**: Fetch past Lotto Max winning numbers from OLG.ca and store them in a local SQLite database.

**Language**: Python 3.10+  
**Location**: `/Users/harpreetsingh/PycharmProjects/numberChurner/`  
**Database engine**: SQLite (stdlib `sqlite3`, no ORM)  
**Only external dependency**: `requests` (see `requirements.txt`)

---

## Discovered API (Critical Context)

The OLG website does NOT expose a public API. An internal gateway API was discovered by inspecting browser network traffic on:
`https://www.olg.ca/en/lottery/play-lotto-max-encore/past-results.html`

### Endpoint
```
GET https://gateway.www.olg.ca/feeds/past-winning-numbers
    ?game=lottomax
    &startDate=YYYY-MM-DD
    &endDate=YYYY-MM-DD
```

### Required HTTP Headers
| Header | Value | Notes |
|--------|-------|-------|
| `Referer` | `https://www.olg.ca/` | Required — proves origin |
| `x-site-code` | `playolg.ca` | Static label |
| `x-client-id` | `9c92a16d25b542048aa93a397093efe2` | Static web client key extracted from OLG frontend. **If scraper returns 401, this needs updating.** |
| `x-correlation-token` | UUID v4 | Must be freshly generated per request |
| `Accept` | `application/json` | |
| `User-Agent` | Modern browser string | |

### JSON Response Structure
```json
{
  "response": {
    "statusCode": "0",
    "winnings": {
      "lottomax": {
        "draw": [
          {
            "date": "2026-02-27",
            "day": "Fri",
            "main": {
              "regular": "07,09,22,24,34,36,37",
              "bonus": "19",
              "prizeShares": {
                "prize": [
                  { "match": "7/7", "winningTickets": "0", "amount": "$70,000,000.00" },
                  { "match": "6/7 + Bonus", "winningTickets": "0", "amount": "$289,736.60" },
                  { "match": "3/7", "winningTickets": "855830", "amount": "FREE PLAY" }
                ]
              }
            },
            "maxmillions": {
              "numbers": ["01,03,05,08,14,32,46", "01,17,22,29,38,45,46"],
              "prizeShares": {
                "prize": [
                  { "match": "01,03,05,08,14,32,46", "winningTickets": "0", "amount": "$1,000,000.00" }
                ]
              }
            },
            "encore": {
              "number": "4159018",
              "prizeShares": {
                "prize": [
                  { "match": "4159018", "winningTickets": "0", "amount": "$1,000,000.00" }
                ]
              }
            }
          }
        ]
      }
    }
  }
}
```

### Known Constraints
- The **OLG website UI** limits date lookups to ~1 year back, but the **API itself** may serve older data.
- Draw days are **Tuesday and Friday** only.
- The API fetches one month of data per call. The scraper iterates month-by-month.
- Delay between requests: **0.75 seconds** (polite scraping, adjustable in `config.py`).
- The API returns 401 without the correct headers (especially `x-client-id`).

---

## File-by-File Summary

### `config.py`
- Constants: `API_BASE_URL`, `GAME`, `OLG_CLIENT_ID`, `REQUEST_DELAY_SECONDS`
- `DEFAULT_START_DATE` = `2019-01-01`, `DEFAULT_END_DATE` = today
- `build_headers()` → dict — generates fresh `x-correlation-token` UUID each call

### `db.py`
- `get_connection(db_path)` → opens/creates SQLite DB
- `init_db(conn)` → runs DDL to create 3 tables if missing
- `upsert_draw(conn, draw_dict)` → `INSERT OR IGNORE` on `draw_date` PK; returns `True` if new
- **Tables**: `draws` (PK: `draw_date`), `maxmillions` (FK → draws), `prize_breakdown` (FK → draws)

### `scraper.py`
- `fetch_month(session, year, month)` → calls API, returns raw JSON or None on error
- `parse_draws(api_json)` → extracts draw list from JSON path `response.winnings.lottomax.draw[]`
- `scrape_range(conn, start_date, end_date)` → main loop: generates list of (year, month) tuples, fetches, parses, upserts, prints progress; returns `(inserted, skipped)`

### `main.py`
- `argparse` CLI: `--start`, `--end`, `--db`
- Calls `get_connection` → `init_db` → `scrape_range` → prints summary
- Entry point: `python main.py`

### `requirements.txt`
```
requests>=2.31.0
```

---

## Database Schema

```sql
CREATE TABLE draws (
    draw_date       TEXT PRIMARY KEY,   -- "YYYY-MM-DD"
    day_of_week     TEXT,               -- "Fri" | "Tue"
    main_numbers    TEXT,               -- "07,09,22,24,34,36,37"
    bonus_number    TEXT,               -- "19"
    encore_number   TEXT                -- "4159018" or NULL
);

CREATE TABLE maxmillions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_date   TEXT NOT NULL REFERENCES draws(draw_date) ON DELETE CASCADE,
    numbers     TEXT NOT NULL           -- "01,03,05,08,14,32,46"
);

CREATE TABLE prize_breakdown (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_date   TEXT NOT NULL REFERENCES draws(draw_date) ON DELETE CASCADE,
    game_type   TEXT NOT NULL,          -- "main" | "encore" | "maxmillions"
    match_desc  TEXT,
    winners     TEXT,
    prize_amount TEXT
);
```

---

## How to Run

```bash
cd /Users/harpreetsingh/PycharmProjects/numberChurner
pip install -r requirements.txt

# Fetch recent ~3 months (quick test):
python main.py --start 2026-01-01 --db test_lotto.db

# Full historical fetch (slow, ~80+ months):
python main.py --start 2019-01-01

# Re-run is always safe — deduplication is handled by INSERT OR IGNORE on draw_date PK
```

---

## Status as of 2026-03-22

| Task | Status |
|------|--------|
| Research OLG.ca & discover gateway API | ✅ Done |
| Write `config.py` | ✅ Done |
| Write `db.py` | ✅ Done |
| Write `scraper.py` | ✅ Done |
| Write `main.py` | ✅ Done |
| Write `requirements.txt` | ✅ Done |
| Write `README.md` | ✅ Done |
| Write `CHECKPOINT.md` | ✅ Done |
| Verify scraper against live OLG API | ✅ Done — 23 draws fetched (Jan–Mar 2026) |
| Deduplication verified | ✅ Done — re-run = 0 new inserts |

### Python Version Note
The code was fixed for **Python 3.9 compatibility** (system Python on macOS):
- `dict | None` → `Optional[Dict]` (from `typing`)
- `list[dict]` → `List[Dict]` (from `typing`)
- `tuple[int, int]` → `Tuple[int, int]` (from `typing`)

The code works on Python 3.9+.

---

## Potential Future Enhancements

- Add `--format csv` option to export DB to CSV
- Add a `--update` mode that only fetches since the most recent draw already in DB
- Add a `lotto649` mode (same API, `game=lotto649`)
- PostgreSQL backend option for multi-user deployments
- Add unit tests for `parse_draws()` using fixture JSON

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `401 Unauthorized` from API | `x-client-id` has been rotated | Inspect network traffic on olg.ca, update `OLG_CLIENT_ID` in `config.py` |
| `0 draws returned` for old dates | API doesn't serve data that far back | Try a more recent `--start` date (2023+) |
| Duplicate draws in DB | Should not happen — `INSERT OR IGNORE` by `draw_date` PK | Check `draw_date` column for expected values |

# Lotto Scraper

A Python CLI toolset that pulls **past Lotto Max winning numbers** storing them in a local **SQLite** database.

---

## Data Coverage

- **2025-02 to Present**: Full detail (MaxMillions, Prize Breakdowns) 

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the historical backfill
python historical_scraper.py

# 3. Fetch recent data from OLG
python main.py --start 2025-01-01

# 4. Inspect the database
sqlite3 lotto_max.db "SELECT COUNT(*) FROM draws;"
```

---

**Examples**

```bash
# Fetch all of 2025
python main.py --start 2025-01-01 --end 2025-12-31

# Fetch recent month into a separate DB
python main.py --start 2026-03-01 --db march2026.db

# Re-run is safe — already-fetched draws are skipped (deduplicated by draw date)
python main.py --start 2025-01-01
```

---

## Database Schema

```
draws               — one row per draw
  draw_date (PK)    TEXT   e.g. "2026-03-21"
  day_of_week       TEXT   e.g. "Fri"
  main_numbers      TEXT   e.g. "07,09,22,24,34,36,37"
  bonus_number      TEXT   e.g. "19"
  encore_number     TEXT   e.g. "4159018"  (NULL if not recorded)

maxmillions         — MaxMillions number sets (multiple per draw)
  id                INTEGER PK
  draw_date         FK → draws.draw_date
  numbers           TEXT   e.g. "01,03,05,08,14,32,46"

prize_breakdown     — prize tier info per draw
  id                INTEGER PK
  draw_date         FK → draws.draw_date
  game_type         TEXT   "main" | "encore" | "maxmillions"
  match_desc        TEXT   e.g. "7/7", "6/7 + Bonus"
  winners           TEXT   number of winning tickets
  prize_amount      TEXT   e.g. "$70,000,000.00" or "FREE PLAY"
```

---

## How It Works

1. **No web scraping** — the tool calls OLG's internal JSON gateway:
   `https://gateway.www.olg.ca/feeds/past-winning-numbers?game=lottomax&startDate=…&endDate=…`
2. It iterates **month by month** with a ≈0.75 s delay between requests to be polite.
3. Each draw is upserted by `draw_date` (primary key) — safe to re-run at any time.

> **Note**: The OLG gateway requires specific HTTP headers (`x-client-id`, `x-site-code`, etc.) extracted from their public website. If the API starts returning `401`, update `OLG_CLIENT_ID` in `config.py` with the value found by inspecting network traffic on [olg.ca](https://www.olg.ca/en/lottery/play-lotto-max-encore/past-results.html).

---
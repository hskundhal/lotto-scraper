"""
scraper.py — Fetch Lotto Max past winning numbers from the OLG gateway API
             and parse the JSON response into draw dicts for storage.
"""

import calendar
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import API_BASE_URL, GAME, REQUEST_DELAY_SECONDS, build_headers
from db import upsert_draw


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_month(session: requests.Session, year: int, month: int) -> Optional[Dict]:
    """
    Fetch all Lotto Max draws for a single calendar month.
    Returns the parsed JSON dict on success, or None on failure.
    """
    first_day = date(year, month, 1)
    last_day  = date(year, month, calendar.monthrange(year, month)[1])

    params = {
        "game":      GAME,
        "startDate": first_day.isoformat(),
        "endDate":   last_day.isoformat(),
    }

    try:
        resp = session.get(
            API_BASE_URL,
            params=params,
            headers=build_headers(),   # fresh x-correlation-token per request
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    except requests.HTTPError as exc:
        print(f"  [HTTP {exc.response.status_code}] {year}-{month:02d} — skipping.")
        return None
    except requests.RequestException as exc:
        print(f"  [Error] {year}-{month:02d}: {exc} — skipping.")
        return None


# ── Parsing ────────────────────────────────────────────────────────────────────

def _parse_prizes(prize_list: List[Dict], game_type: str) -> List[Dict]:
    """Convert a raw prize list into a normalised list of dicts."""
    out = []
    for p in prize_list:
        out.append({
            "game_type":    game_type,
            "match_desc":   p.get("match"),
            "winners":      p.get("winningTickets"),
            "prize_amount": p.get("amount"),
        })
    return out


def parse_draws(api_json: Dict) -> List[Dict[str, Any]]:
    """
    Navigate the OLG JSON structure and return a flat list of draw dicts.

    JSON path: response → winnings → lottomax → draw[]
    """
    try:
        draws_raw = (
            api_json["response"]["winnings"]["lottomax"]["draw"]
        )
    except (KeyError, TypeError):
        return []

    results = []
    for raw in draws_raw:
        draw_date = raw.get("date")  # "YYYY-MM-DD"
        if not draw_date:
            continue

        # ── Main numbers ──────────────────────────────────────────────────────
        main      = raw.get("main", {})
        main_nums  = main.get("regular", "")   # "07,09,22,24,34,36,37"
        bonus_num  = main.get("bonus", "")

        # ── Encore ────────────────────────────────────────────────────────────
        encore     = raw.get("encore", {})
        encore_num = encore.get("number")      # None if absent

        # ── MaxMillions ───────────────────────────────────────────────────────
        maxm       = raw.get("maxmillions", {})
        maxm_nums  = maxm.get("numbers", [])   # list of "NN,NN,NN,NN,NN,NN,NN"

        # ── Prize breakdown ───────────────────────────────────────────────────
        prizeshares: list[dict] = []

        main_prizes = main.get("prizeShares", {}).get("prize", [])
        prizeshares.extend(_parse_prizes(main_prizes, "main"))

        encore_prizes = encore.get("prizeShares", {}).get("prize", [])
        prizeshares.extend(_parse_prizes(encore_prizes, "encore"))

        maxm_prizes = maxm.get("prizeShares", {}).get("prize", [])
        prizeshares.extend(_parse_prizes(maxm_prizes, "maxmillions"))

        results.append({
            "draw_date":          draw_date,
            "day_of_week":        raw.get("day"),
            "main_numbers":       main_nums,
            "bonus_number":       bonus_num,
            "encore_number":      encore_num,
            "maxmillions_numbers": maxm_nums,
            "prize_breakdown":    prizeshares,
        })

    return results


# ── Orchestration ──────────────────────────────────────────────────────────────

def scrape_range(
    conn,
    start_date: date,
    end_date: date,
) -> Tuple[int, int]:
    """
    Iterate month by month between *start_date* and *end_date* (inclusive),
    fetch draws from the OLG API, parse them, and upsert into the DB.

    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped  = 0

    # Build list of (year, month) tuples to fetch
    months: list[tuple[int, int]] = []
    cursor = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while cursor <= end_month:
        months.append((cursor.year, cursor.month))
        # Advance one month
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    total_months = len(months)

    with requests.Session() as session:
        for idx, (year, month) in enumerate(months, start=1):
            print(
                f"  Fetching {year}-{month:02d}  "
                f"({idx}/{total_months}) ...",
                end=" ",
                flush=True,
            )

            api_json = fetch_month(session, year, month)
            if api_json is None:
                print()
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            draws = parse_draws(api_json)
            month_inserted = 0
            month_skipped  = 0

            for draw in draws:
                if upsert_draw(conn, draw):
                    month_inserted += 1
                else:
                    month_skipped += 1

            inserted += month_inserted
            skipped  += month_skipped

            print(f"✓  +{month_inserted} new, {month_skipped} already in DB")

            # Polite delay — skip on the very last request
            if idx < total_months:
                time.sleep(REQUEST_DELAY_SECONDS)

    return inserted, skipped

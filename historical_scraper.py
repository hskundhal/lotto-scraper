"""
historical_scraper.py — Scrape historical Lotto Max winning numbers from
lottomaxnumbers.com and upsert them into the existing lotto_max.db SQLite DB.

Source: https://www.lottomaxnumbers.com/numbers/YYYY
Structure:
  - One page per year, URL: /numbers/YYYY
  - Table: table.resultsTable
  - Per row: draw date (col 1), number balls (col 2), jackpot (col 3)
  - Main numbers: ul.balls > li.ball
  - Bonus number:  ul.balls > li.bonus-ball
  - Date format on site: "Month DD YYYY"  (e.g. "January 03 2023")

Note: This source does NOT include MaxMillions draw numbers or prize breakdown
detail on the year summary pages. Those fields will be NULL for historically
backfilled draws. The OLG API already covers ~Feb 2025 onward with full detail.

Usage:
  python historical_scraper.py                     # 2009–2025 (all historic)
  python historical_scraper.py --start 2015 --end 2020
  python historical_scraper.py --db lotto_max.db
"""

import argparse
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

from db import get_connection, init_db, upsert_draw

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_URL      = "https://www.lottomaxnumbers.com/numbers/{year}"
LOTTO_LAUNCH  = 2009   # First Lotto Max draw: September 25, 2009
REQUEST_DELAY = 1.5    # seconds between page requests (be polite)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
    "Referer": "https://www.lottomaxnumbers.com/",
}


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_year_page(session: requests.Session, year: int) -> Optional[str]:
    """Fetch the HTML for a single year page. Returns HTML string or None."""
    url = BASE_URL.format(year=year)
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except requests.HTTPError as exc:
        print(f"  [HTTP {exc.response.status_code}] {year} — skipping.")
        return None
    except requests.RequestException as exc:
        print(f"  [Error] {year}: {exc} — skipping.")
        return None


# ── Parsing ────────────────────────────────────────────────────────────────────

def _parse_date(raw: str) -> Optional[str]:
    """
    Convert "January 03 2023" → "2023-01-03".
    Returns None if parsing fails.
    """
    raw = raw.strip()
    # Remove any extra whitespace / newlines
    raw = " ".join(raw.split())
    for fmt in ("%B %d %Y", "%B %d, %Y", "%b %d %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_year_page(html: str, year: int) -> List[Dict[str, Any]]:
    """
    Parse all draw rows from a lottomaxnumbers.com year page.
    Returns a list of draw dicts compatible with db.upsert_draw().
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="resultsTable")
    if not table:
        return []

    draws = []
    rows = table.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue  # skip header rows

        # ── Draw date ─────────────────────────────────────────────────────────
        date_cell = cols[0]
        # The date text is in a link; strip badge text ("With Max Millions!")
        date_link = date_cell.find("a")
        raw_date_text = date_link.get_text(separator=" ", strip=True) if date_link else date_cell.get_text(strip=True)
        draw_date = _parse_date(raw_date_text)
        if not draw_date:
            continue  # couldn't parse date, skip

        # ── Numbers ───────────────────────────────────────────────────────────
        number_cell = cols[1]
        balls      = number_cell.find_all("li", class_="ball")
        bonus_ball = number_cell.find("li", class_="bonus-ball")

        main_nums = ",".join(
            b.get_text(strip=True).zfill(2) for b in balls
        ) if balls else ""

        bonus_num = bonus_ball.get_text(strip=True).zfill(2) if bonus_ball else ""

        # ── Day of week (derive from date) ────────────────────────────────────
        try:
            day_of_week = datetime.strptime(draw_date, "%Y-%m-%d").strftime("%a")
        except ValueError:
            day_of_week = None

        draws.append({
            "draw_date":           draw_date,
            "day_of_week":         day_of_week,
            "main_numbers":        main_nums,
            "bonus_number":        bonus_num,
            "encore_number":       None,   # not available on this source
            "maxmillions_numbers": [],     # not available on summary page
            "prize_breakdown":     [],     # not available on summary page
        })

    return draws


# ── Main loop ──────────────────────────────────────────────────────────────────

def scrape_historical(
    conn,
    start_year: int,
    end_year: int,
) -> tuple:
    """
    Scrape lottomaxnumbers.com year by year and upsert draws into *conn*.
    Returns (inserted, skipped).
    """
    inserted = 0
    skipped  = 0
    years    = list(range(start_year, end_year + 1))

    with requests.Session() as session:
        for idx, year in enumerate(years, start=1):
            print(f"  Fetching {year}  ({idx}/{len(years)}) ...", end=" ", flush=True)

            html = fetch_year_page(session, year)
            if html is None:
                print()
                time.sleep(REQUEST_DELAY)
                continue

            draws = parse_year_page(html, year)
            yr_inserted = 0
            yr_skipped  = 0

            for draw in draws:
                if upsert_draw(conn, draw):
                    yr_inserted += 1
                else:
                    yr_skipped += 1

            inserted += yr_inserted
            skipped  += yr_skipped

            print(f"✓  {len(draws)} draws parsed  |  +{yr_inserted} new, {yr_skipped} already in DB")

            if idx < len(years):
                time.sleep(REQUEST_DELAY)

    return inserted, skipped


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    import sys
    from config import DEFAULT_DB_PATH

    parser = argparse.ArgumentParser(
        description=(
            "Backfill historic Lotto Max results from lottomaxnumbers.com "
            "into the SQLite database."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--start", type=int, default=LOTTO_LAUNCH,
        metavar="YYYY", help="First year to fetch (default: 2009, Lotto Max launch)",
    )
    parser.add_argument(
        "--end", type=int, default=2025,
        metavar="YYYY", help="Last year to fetch (use 2025 to avoid overlap with OLG API data)",
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB_PATH, metavar="PATH",
        help="Path to the SQLite database file",
    )

    args = parser.parse_args()

    if args.start > args.end:
        print("Error: --start must be <= --end", file=sys.stderr)
        sys.exit(1)

    if args.end > 2025:
        print(
            "Warning: OLG API already covers Feb 2025 onward. "
            "Run main.py to fetch that data instead.",
        )

    print(f"Database   : {args.db}")
    print(f"Years      : {args.start} → {args.end}")
    print(f"Source     : lottomaxnumbers.com")
    print()

    conn = get_connection(args.db)
    init_db(conn)

    print("Scraping historical draws …")
    print("-" * 55)

    inserted, skipped = scrape_historical(conn, args.start, args.end)
    conn.close()

    print("-" * 55)
    print(f"Done.  {inserted} new draw(s) added, {skipped} already in DB.")


if __name__ == "__main__":
    main()

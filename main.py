"""
main.py — CLI entry point for the Lotto Max OLG past-results scraper.

Usage
-----
  python main.py                              # fetch 2019-01-01 to today
  python main.py --start 2024-01-01           # narrow the start date
  python main.py --start 2026-01-01 --end 2026-03-22
  python main.py --db my_custom.db            # custom DB file path
"""

import argparse
import sqlite3
import sys
from datetime import date, datetime

from config import DEFAULT_DB_PATH, DEFAULT_END_DATE, DEFAULT_START_DATE
from db import get_connection, init_db
from scraper import scrape_range


def parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{s}' — expected format: YYYY-MM-DD"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch past Lotto Max winning numbers from OLG.ca and store them in SQLite.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        type=parse_date,
        default=DEFAULT_START_DATE,
        help="Start date for the fetch range",
    )
    parser.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        type=parse_date,
        default=DEFAULT_END_DATE,
        help="End date for the fetch range (inclusive)",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file (created if it does not exist)",
    )

    args = parser.parse_args()

    if args.start > args.end:
        print("Error: --start must be on or before --end.", file=sys.stderr)
        sys.exit(1)

    print(f"Database : {args.db}")
    print(f"Range    : {args.start}  →  {args.end}")
    print()

    conn: sqlite3.Connection = get_connection(args.db)
    init_db(conn)

    print("Scraping OLG past-winning-numbers API …")
    print("-" * 50)

    inserted, skipped = scrape_range(conn, args.start, args.end)
    conn.close()

    print("-" * 50)
    print(f"Done.  {inserted} new draw(s) added, {skipped} already in DB.")

    if inserted == 0 and skipped == 0:
        print(
            "\nNote: No draws were returned by the API for that date range.\n"
            "The OLG gateway may only serve recent data. Try a more recent --start date."
        )


if __name__ == "__main__":
    main()

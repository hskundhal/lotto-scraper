"""
config.py — Configuration constants for the Lotto Max OLG scraper.
"""

import uuid
from datetime import date

# ── OLG Gateway API ───────────────────────────────────────────────────────────
API_BASE_URL = "https://gateway.www.olg.ca/feeds/past-winning-numbers"
GAME = "lottomax"

# Static client ID extracted from OLG's public web frontend.
# If the API starts returning 401, re-inspect network traffic on olg.ca to get
# the current value.
OLG_CLIENT_ID = "9c92a16d25b542048aa93a397093efe2"

def build_headers() -> dict:
    """Return the HTTP headers required by the OLG gateway API."""
    return {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.olg.ca/",
        "x-site-code": "playolg.ca",
        "x-client-id": OLG_CLIENT_ID,
        # A fresh UUID is required per request (per OLG session behaviour).
        "x-correlation-token": str(uuid.uuid4()),
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
    }


# ── Default date range ────────────────────────────────────────────────────────
# Lotto Max launched in September 2009. Start from 2019 by default as a
# conservative baseline; the API may not have data going back further.
DEFAULT_START_DATE = date(2019, 1, 1)
DEFAULT_END_DATE = date.today()

# ── Database ──────────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = "lotto_max.db"

# ── Politeness delay (seconds between HTTP requests) ─────────────────────────
REQUEST_DELAY_SECONDS = 0.75

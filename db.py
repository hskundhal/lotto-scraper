"""
db.py — SQLite schema creation and data upsert helpers.

Tables
------
draws           — one row per Lotto Max draw (draw_date is the primary key)
maxmillions     — MaxMillions number sets for draws where the jackpot was high enough
prize_breakdown — per-tier prize information for main, encore, and maxmillions
"""

import sqlite3
from typing import Any, Dict


# ── Schema ────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS draws (
    draw_date       TEXT PRIMARY KEY,   -- ISO 8601: YYYY-MM-DD
    day_of_week     TEXT,               -- e.g. "Fri", "Tue"
    main_numbers    TEXT,               -- e.g. "07,09,22,24,34,36,37"
    bonus_number    TEXT,               -- e.g. "19"
    encore_number   TEXT                -- 7-digit encore number, may be NULL
);

CREATE TABLE IF NOT EXISTS maxmillions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_date   TEXT NOT NULL REFERENCES draws(draw_date) ON DELETE CASCADE,
    numbers     TEXT NOT NULL           -- e.g. "01,03,05,08,14,32,46"
);

CREATE TABLE IF NOT EXISTS prize_breakdown (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_date   TEXT NOT NULL REFERENCES draws(draw_date) ON DELETE CASCADE,
    game_type   TEXT NOT NULL,          -- "main", "encore", or "maxmillions"
    match_desc  TEXT,                   -- e.g. "7/7", "6/7 + Bonus", "______8"
    winners     TEXT,                   -- number of winning tickets (stored as text)
    prize_amount TEXT                   -- e.g. "$70,000,000.00" or "FREE PLAY"
);

CREATE INDEX IF NOT EXISTS idx_maxm_date ON maxmillions(draw_date);
CREATE INDEX IF NOT EXISTS idx_prize_date ON prize_breakdown(draw_date);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not already exist."""
    conn.executescript(DDL)
    conn.commit()


# ── Upsert helpers ─────────────────────────────────────────────────────────────

def upsert_draw(conn: sqlite3.Connection, draw: Dict[str, Any]) -> bool:
    """
    Insert a single draw record.  Returns True if a new row was inserted,
    False if the draw already existed in the DB (deduplication via INSERT OR IGNORE).

    Expected keys in `draw`:
        draw_date, day_of_week, main_numbers, bonus_number,
        encore_number,
        maxmillions_numbers  (list[str]),
        prize_breakdown      (list[dict] each with game_type, match_desc, winners, prize_amount)
    """
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO draws
            (draw_date, day_of_week, main_numbers, bonus_number, encore_number)
        VALUES
            (:draw_date, :day_of_week, :main_numbers, :bonus_number, :encore_number)
        """,
        {
            "draw_date":     draw["draw_date"],
            "day_of_week":   draw.get("day_of_week"),
            "main_numbers":  draw.get("main_numbers"),
            "bonus_number":  draw.get("bonus_number"),
            "encore_number": draw.get("encore_number"),
        },
    )

    inserted = cur.rowcount == 1  # 0 means it already existed

    if inserted:
        # MaxMillions numbers (may be absent for low jackpot draws)
        for numbers_str in draw.get("maxmillions_numbers", []):
            cur.execute(
                "INSERT INTO maxmillions (draw_date, numbers) VALUES (?, ?)",
                (draw["draw_date"], numbers_str),
            )

        # Prize breakdown rows
        for pb in draw.get("prize_breakdown", []):
            cur.execute(
                """
                INSERT INTO prize_breakdown
                    (draw_date, game_type, match_desc, winners, prize_amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    draw["draw_date"],
                    pb.get("game_type"),
                    pb.get("match_desc"),
                    pb.get("winners"),
                    pb.get("prize_amount"),
                ),
            )

    conn.commit()
    return inserted


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open (or create) a SQLite database at *db_path* and return the connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

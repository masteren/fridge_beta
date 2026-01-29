import sqlite3
from pathlib import Path
from typing import List, Dict, Any

DB_PATH = Path(__file__).with_name("db.sqlite3")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL
            )
            """
        )
        conn.commit()


def fetch_ingredients() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, quantity, unit FROM ingredients ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def add_ingredient(name: str, quantity: int, unit: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ingredients (name, quantity, unit) VALUES (?, ?, ?)",
            (name, quantity, unit),
        )
        conn.commit()


def delete_ingredient(item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM ingredients WHERE id = ?", (item_id,))
        conn.commit()

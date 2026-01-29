import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).with_name("db.sqlite3")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pantry_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL,
                UNIQUE(user_id, name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                ingredients_json TEXT NOT NULL,
                nutrition_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cooking_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipe_id INTEGER NOT NULL,
                cooked_at_date TEXT NOT NULL
            )
            """
        )
        conn.commit()


def seed_data() -> None:
    with get_connection() as conn:
        demo_user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            ("demo",),
        ).fetchone()
        if demo_user is None:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (
                    "demo",
                    "pbkdf2:sha256:1000000$gQLDNfGQnN60FqKe$fe708358bcb78e009d01c7d85880f9df243e058bc97ba430c5f98e593a8bdcd0",
                ),
            )
            demo_user_id = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                ("demo",),
            ).fetchone()["id"]
        else:
            demo_user_id = demo_user["id"]
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (
                    "pbkdf2:sha256:1000000$gQLDNfGQnN60FqKe$fe708358bcb78e009d01c7d85880f9df243e058bc97ba430c5f98e593a8bdcd0",
                    demo_user_id,
                ),
            )

        pantry_seed = [
            ("鶏むね肉", 2, "枚"),
            ("卵", 6, "個"),
            ("ブロッコリー", 1, "株"),
            ("ご飯", 2, "杯"),
            ("牛乳", 1, "本"),
            ("豆腐", 1, "丁"),
        ]
        for name, qty, unit in pantry_seed:
            conn.execute(
                """
                INSERT INTO pantry_items (user_id, name, quantity, unit)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, name)
                DO NOTHING
                """,
                (demo_user_id, name, qty, unit),
            )

        recipe_count = conn.execute("SELECT COUNT(*) as count FROM recipes").fetchone()[
            "count"
        ]
        if recipe_count == 0:
            recipes = [
                {
                    "title": "鶏むね肉とブロッコリーの蒸し焼き",
                    "description": "高たんぱくで軽めの一皿。",
                    "steps": [
                        "鶏むね肉に塩こしょうをする",
                        "ブロッコリーと一緒に蒸し焼きにする",
                        "レモンで仕上げる",
                    ],
                    "ingredients": [
                        {"name": "鶏むね肉", "quantity": 1, "unit": "枚"},
                        {"name": "ブロッコリー", "quantity": 1, "unit": "株"},
                    ],
                    "nutrition": {
                        "kcal": 420,
                        "protein": 48,
                        "fat": 9,
                        "carb": 18,
                        "salt": 1.2,
                        "veg_score": 2,
                    },
                },
                {
                    "title": "豆腐と卵のふわとろ丼",
                    "description": "手軽な朝食向けメニュー。",
                    "steps": [
                        "豆腐を温めて崩す",
                        "溶き卵を加えて半熟にする",
                        "ご飯にのせて醤油を垂らす",
                    ],
                    "ingredients": [
                        {"name": "豆腐", "quantity": 1, "unit": "丁"},
                        {"name": "卵", "quantity": 2, "unit": "個"},
                        {"name": "ご飯", "quantity": 1, "unit": "杯"},
                    ],
                    "nutrition": {
                        "kcal": 520,
                        "protein": 32,
                        "fat": 14,
                        "carb": 60,
                        "salt": 1.5,
                        "veg_score": 1,
                    },
                },
                {
                    "title": "トマトと玉ねぎのミルクスープ",
                    "description": "野菜を補えるやさしいスープ。",
                    "steps": [
                        "玉ねぎとトマトを炒める",
                        "牛乳と水を加えて煮込む",
                        "塩で味を整える",
                    ],
                    "ingredients": [
                        {"name": "トマト", "quantity": 2, "unit": "個"},
                        {"name": "玉ねぎ", "quantity": 1, "unit": "個"},
                        {"name": "牛乳", "quantity": 1, "unit": "本"},
                    ],
                    "nutrition": {
                        "kcal": 300,
                        "protein": 12,
                        "fat": 10,
                        "carb": 32,
                        "salt": 0.8,
                        "veg_score": 3,
                    },
                },
                {
                    "title": "鶏むね肉とご飯のスタミナボウル",
                    "description": "運動後の補給に最適。",
                    "steps": [
                        "鶏むね肉を炒めて香ばしくする",
                        "ご飯にのせて温泉卵を添える",
                        "タレで味付けする",
                    ],
                    "ingredients": [
                        {"name": "鶏むね肉", "quantity": 1, "unit": "枚"},
                        {"name": "ご飯", "quantity": 1, "unit": "杯"},
                        {"name": "卵", "quantity": 1, "unit": "個"},
                    ],
                    "nutrition": {
                        "kcal": 640,
                        "protein": 45,
                        "fat": 18,
                        "carb": 70,
                        "salt": 2.0,
                        "veg_score": 1,
                    },
                },
            ]
            for recipe in recipes:
                conn.execute(
                    """
                    INSERT INTO recipes
                        (title, description, steps_json, ingredients_json, nutrition_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recipe["title"],
                        recipe["description"],
                        json.dumps(recipe["steps"], ensure_ascii=False),
                        json.dumps(recipe["ingredients"], ensure_ascii=False),
                        json.dumps(recipe["nutrition"], ensure_ascii=False),
                    ),
                )
        conn.commit()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password_hash: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return cursor.lastrowid


def fetch_pantry_items(user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, quantity, unit
            FROM pantry_items
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_pantry_item(user_id: int, name: str, quantity: int, unit: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pantry_items (user_id, name, quantity, unit)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, name)
            DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (user_id, name, quantity, unit),
        )
        conn.commit()


def update_pantry_item(
    user_id: int, item_id: int, name: str, quantity: int, unit: str
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pantry_items
            SET name = ?, quantity = ?, unit = ?
            WHERE id = ? AND user_id = ?
            """,
            (name, quantity, unit, item_id, user_id),
        )
        conn.commit()


def delete_pantry_item(user_id: int, item_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM pantry_items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )
        conn.commit()


def fetch_recipes() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, description, steps_json, ingredients_json, nutrition_json
            FROM recipes
            ORDER BY id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_recipe_by_id(recipe_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, description, steps_json, ingredients_json, nutrition_json
            FROM recipes
            WHERE id = ?
            """,
            (recipe_id,),
        ).fetchone()
    return dict(row) if row else None


def add_cooking_log(user_id: int, recipe_id: int, cooked_at_date: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cooking_log (user_id, recipe_id, cooked_at_date)
            VALUES (?, ?, ?)
            """,
            (user_id, recipe_id, cooked_at_date),
        )
        conn.commit()


def fetch_cooking_logs_range(
    user_id: int, start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, recipe_id, cooked_at_date
            FROM cooking_log
            WHERE user_id = ? AND cooked_at_date BETWEEN ? AND ?
            ORDER BY cooked_at_date ASC
            """,
            (user_id, start_date, end_date),
        ).fetchall()
    return [dict(row) for row in rows]

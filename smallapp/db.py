# -*- coding: utf-8 -*-
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from recipes_data import INTERNATIONAL_RECIPES

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
                expiry_date TEXT,
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
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_canonical TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                recipe_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                amount REAL,
                unit TEXT,
                role TEXT NOT NULL,
                PRIMARY KEY (recipe_id, ingredient_id, role),
                FOREIGN KEY (recipe_id) REFERENCES recipes(id),
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingredient_alias (
                alias TEXT PRIMARY KEY,
                ingredient_id INTEGER NOT NULL,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recognition_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recognized_at TEXT NOT NULL,
                items_count INTEGER NOT NULL
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
                    "pbkdf2:sha256:1000000$0nVv9qO3JP71ILXS$401974b385d6b086d4dc74fa1ae28894a0341ee9b5517b809c73cad21da2d344",
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
                    "pbkdf2:sha256:1000000$0nVv9qO3JP71ILXS$401974b385d6b086d4dc74fa1ae28894a0341ee9b5517b809c73cad21da2d344",
                    demo_user_id,
                ),
            )

        new_user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            ("newone",),
        ).fetchone()
        if new_user is None:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (
                    "newone",
                    "pbkdf2:sha256:1000000$lLhtdkq6Pt8yXZyN$de7590a562dad6787e3516dc5dfa14446f748643e9e9f067b77f51d80c071968",
                ),
            )
        else:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (
                    "pbkdf2:sha256:1000000$lLhtdkq6Pt8yXZyN$de7590a562dad6787e3516dc5dfa14446f748643e9e9f067b77f51d80c071968",
                    new_user["id"],
                ),
            )

        pantry_seed = [
            # 易失商品 (1-3天内过期)
            ("鸡蛋", 2, "个", (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")),
            ("牛奶", 1, "盒", (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")),
            ("豆腐", 2, "块", (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")),
            ("番茄", 8, "个", (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")),
            ("牛肉", 1, "斤", (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")),
            # 中期食材 (7-15天)
            ("菠菜", 3, "把", (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")),
            ("胡萝卜", 3, "个", (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d")),
            ("土豆", 2, "个", (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")),
            ("洋葱", 5, "个", (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")),
            ("葱", 3, "斤", (datetime.now() + timedelta(days=18)).strftime("%Y-%m-%d")),
            # 长期食材
            ("盐", 1, "袋", (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")),
            ("油", 1, "斤", (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")),
            ("酱油", 1, "斤", (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")),
            ("砂糖", 1, "袋", (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")),
            ("小麦粉", 1, "袋", (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")),
            # 冷冻食品
            ("冷冻鸡腿", 2, "袋", (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d")),
            ("冷冻饺子", 1, "盒", (datetime.now() + timedelta(days=40)).strftime("%Y-%m-%d")),
            # 饮料和其他
            ("番茄酱", 1, "袋", (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")),
            ("面条", 3, "个", (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")),
            ("大米", 1, "袋", (datetime.now() + timedelta(days=25)).strftime("%Y-%m-%d")),
        ]
        for name, qty, unit, expiry_date in pantry_seed:
            conn.execute(
                """
                INSERT INTO pantry_items (user_id, name, quantity, unit, expiry_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name)
                DO UPDATE SET expiry_date = excluded.expiry_date
                """,
                (demo_user_id, name, qty, unit, expiry_date),
            )

        def _insert_recipe(conn, recipe):
            existing = conn.execute(
                "SELECT id FROM recipes WHERE title = ?",
                (recipe["title"],),
            ).fetchone()
            if existing:
                return
            cursor = conn.execute(
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
            recipe_id = cursor.lastrowid
            for idx, ing in enumerate(recipe["ingredients"]):
                ing_name = str(ing.get("name", "")).strip()
                if not ing_name:
                    continue
                ing_id = _get_or_create_ingredient_id(conn, ing_name)
                role = "required" if idx < 2 else "optional"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO recipe_ingredients
                        (recipe_id, ingredient_id, amount, unit, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id,
                        ing_id,
                        ing.get("quantity"),
                        ing.get("unit"),
                        role,
                    ),
                )

        global_recipes = INTERNATIONAL_RECIPES
        for recipe in global_recipes:
            _insert_recipe(conn, recipe)

        # Add cooking history (demonstration data)
        cooking_history = [
            (demo_user_id, 1, (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")),
            (demo_user_id, 2, (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")),
            (demo_user_id, 3, (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")),
            (demo_user_id, 1, (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")),
            (demo_user_id, 4, (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")),
            (demo_user_id, 2, (datetime.now()).strftime("%Y-%m-%d")),
            (demo_user_id, 3, (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")),
            (demo_user_id, 1, (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")),
        ]
        for user_id, recipe_id, cooked_date in cooking_history:
            conn.execute(
                "INSERT INTO cooking_log (user_id, recipe_id, cooked_at_date) VALUES (?, ?, ?)",
                (user_id, recipe_id, cooked_date),
            )

        # Add AI recognition history
        recognition_history = [
            (demo_user_id, (datetime.now() - timedelta(days=8)).isoformat(), 3),
            (demo_user_id, (datetime.now() - timedelta(days=6)).isoformat(), 2),
            (demo_user_id, (datetime.now() - timedelta(days=4)).isoformat(), 5),
            (demo_user_id, (datetime.now() - timedelta(days=2)).isoformat(), 4),
            (demo_user_id, (datetime.now() - timedelta(days=1)).isoformat(), 6),
            (demo_user_id, (datetime.now()).isoformat(), 2),
        ]
        for user_id, recognized_at, items_count in recognition_history:
            conn.execute(
                "INSERT INTO recognition_logs (user_id, recognized_at, items_count) VALUES (?, ?, ?)",
                (user_id, recognized_at, items_count),
            )

        conn.commit()


def _get_or_create_ingredient_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM ingredients WHERE name_canonical = ?",
        (name,),
    ).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO ingredients (name_canonical) VALUES (?)",
        (name,),
    )
    return cursor.lastrowid




def fetch_recipes_with_ingredients() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        recipe_rows = conn.execute(
            """
            SELECT id, title, description, steps_json, ingredients_json, nutrition_json
            FROM recipes
            ORDER BY id ASC
            """
        ).fetchall()
        recipes = [dict(row) for row in recipe_rows]

        ingredient_rows = conn.execute(
            """
            SELECT ri.recipe_id, i.name_canonical, ri.amount, ri.unit, ri.role
            FROM recipe_ingredients ri
            JOIN ingredients i ON i.id = ri.ingredient_id
            ORDER BY ri.recipe_id ASC
            """
        ).fetchall()

    ing_map: Dict[int, List[Dict[str, Any]]] = {}
    for row in ingredient_rows:
        rid = row["recipe_id"]
        ing_map.setdefault(rid, []).append(
            {
                "name": row["name_canonical"],
                "quantity": row["amount"],
                "unit": row["unit"],
                "role": row["role"],
            }
        )

    for recipe in recipes:
        recipe["ingredients"] = ing_map.get(recipe["id"], [])
    return recipes


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
            SELECT id, name, quantity, unit, expiry_date
            FROM pantry_items
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_pantry_item(
    user_id: int,
    name: str,
    quantity: int,
    unit: str,
    expiry_date: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pantry_items (user_id, name, quantity, unit, expiry_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, name)
            DO UPDATE SET
                quantity = quantity + excluded.quantity,
                unit = excluded.unit,
                expiry_date = excluded.expiry_date
            """,
            (user_id, name, quantity, unit, expiry_date),
        )
        conn.commit()


def update_pantry_item(
    user_id: int,
    item_id: int,
    name: str,
    quantity: int,
    unit: str,
    expiry_date: Optional[str],
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pantry_items
            SET name = ?, quantity = ?, unit = ?, expiry_date = ?
            WHERE id = ? AND user_id = ?
            """,
            (name, quantity, unit, expiry_date, item_id, user_id),
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


def add_recognition_log(user_id: int, recognized_at: str, items_count: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO recognition_logs (user_id, recognized_at, items_count)
            VALUES (?, ?, ?)
            """,
            (user_id, recognized_at, items_count),
        )
        conn.commit()


def fetch_recognition_logs(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, recognized_at, items_count
            FROM recognition_logs
            WHERE user_id = ?
            ORDER BY recognized_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_expiry_alerts(user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, quantity, unit, expiry_date
            FROM pantry_items
            WHERE user_id = ? AND expiry_date IS NOT NULL AND expiry_date <= date('now', '+7 days')
            ORDER BY expiry_date ASC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_cooking_log_count(user_id: int) -> int:
    with get_connection() as conn:
        result = conn.execute(
            "SELECT COUNT(DISTINCT recipe_id) as count FROM cooking_log WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return result["count"] if result else 0


def search_recipes(keyword: str) -> List[Dict[str, Any]]:
    """Search recipes by title or description."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, description, ingredients_json, nutrition_json
            FROM recipes
            WHERE LOWER(title) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?)
            ORDER BY title ASC
            """,
            (f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
    return [dict(row) for row in rows]

import hashlib
import json
import os
import random
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import (
    add_cooking_log,
    add_recognition_log,
    create_user,
    fetch_pantry_items,
    fetch_recipe_by_id,
    fetch_recipes,
    fetch_recipes_with_ingredients,
    fetch_recognition_logs,
    fetch_cooking_log_count,
    fetch_expiry_alerts,
    fetch_cooking_logs_range,
    get_user_by_id,
    get_user_by_username,
    init_db,
    seed_data,
    search_recipes,
    upsert_pantry_item,
    update_pantry_item,
    delete_pantry_item,
)
from services.openai_vision import (
    MissingAPIKeyError,
    NonJsonResponseError,
    OpenAIVisionError,
    VisionTimeoutError,
    recognize_ingredients_from_bytes,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


DEMO_IMAGE_GROUPS: Tuple[Tuple[str, str], ...] = (
    ("fridge", "fridege"),
    ("cart", "cart"),
    ("table", "table"),
)
DEMO_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


with app.app_context():
    init_db()
    seed_data()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def _build_demo_catalog() -> List[Dict[str, List[str]]]:
    base_dir = Path(app.root_path) / "static"
    catalog: List[Dict[str, List[str]]] = []
    for key, rel_path in DEMO_IMAGE_GROUPS:
        dir_path = base_dir / rel_path
        images: List[str] = []
        if dir_path.exists():
            files = [
                path
                for path in dir_path.iterdir()
                if path.is_file() and path.suffix.lower() in DEMO_IMAGE_EXTS
            ]
            for path in sorted(files):
                images.append(url_for("static", filename=f"{rel_path}/{path.name}"))
        catalog.append({"key": key, "images": images})
    return catalog


def _demo_cache_path(image_bytes: bytes) -> Path:
    digest = hashlib.sha256(image_bytes).hexdigest()
    cache_dir = Path(app.root_path) / "static" / "demo_cache"
    return cache_dir / f"{digest}.json"


def _read_demo_cache(path: Path) -> Optional[List[Dict[str, object]]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ingredients = payload.get("ingredients")
    if isinstance(ingredients, list):
        return ingredients
    return None


def _write_demo_cache(path: Path, ingredients: List[Dict[str, object]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ingredients": ingredients,
            "cached_at": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return


@app.context_processor
def inject_alert_count():
    """Inject alert count into all templates."""
    user_id = session.get("user_id")
    alert_count = 0
    if user_id:
        expiry_alerts = fetch_expiry_alerts(user_id)
        alert_count = len(expiry_alerts)
    return dict(alert_count=alert_count)


@app.get("/")
def home():
    # Get overview stats for home page
    user_id = session.get("user_id")

    pantry_count = 0
    expiry_alert_count = 0
    recipe_count = 0
    avg_protein = 0

    if user_id:
        # Get stats only if user is logged in
        pantry_items = fetch_pantry_items(user_id)
        pantry_count = len(pantry_items)

        expiry_alerts = fetch_expiry_alerts(user_id)
        expiry_alert_count = len(expiry_alerts)

        recipes_data = fetch_recipes()
        pantry_names = {item["name"] for item in pantry_items}
        recipe_count = sum(1 for recipe in recipes_data
                          if any(ing["name"] in pantry_names
                                for ing in json.loads(recipe["ingredients_json"])))

        # Calculate average protein for the week
        today = date.today()
        last_7_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        labels = [day.isoformat() for day in last_7_days]

        logs = fetch_cooking_logs_range(user_id, labels[0], labels[-1])
        recipes_map = {recipe["id"]: recipe for recipe in recipes_data}

        total_protein = 0
        for log in logs:
            recipe = recipes_map.get(log["recipe_id"])
            if recipe:
                nutrition = json.loads(recipe["nutrition_json"])
                total_protein += nutrition.get("protein", 0)

        avg_protein = int(total_protein / 7) if total_protein > 0 else 0

    return render_template(
        "home.html",
        user=current_user(),
        pantry_count=pantry_count,
        expiry_alert_count=expiry_alert_count,
        recipe_count=recipe_count,
        avg_protein=avg_protein,
    )


@app.get("/auth")
def auth():
    return render_template("auth.html", error=None)


@app.post("/register")
def register():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return render_template("auth.html", error="ユーザー名とパスワードを入力してください")

    if get_user_by_username(username):
        return render_template("auth.html", error="ユーザー名は既に使われています")

    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    user_id = create_user(username, password_hash)
    session["user_id"] = user_id
    return redirect(url_for("dashboard"))


@app.post("/login")
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    user = get_user_by_username(username)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("auth.html", error="ログインに失敗しました")

    session["user_id"] = user["id"]
    return redirect(url_for("dashboard"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    # Get statistics
    recognition_count = len(fetch_recognition_logs(user_id, limit=100))
    recipe_count = fetch_cooking_log_count(user_id)
    expiry_alerts = fetch_expiry_alerts(user_id)

    # Get recent logs
    recognition_logs = fetch_recognition_logs(user_id, limit=3)

    # Get recent cooked recipes
    today = date.today()
    last_7_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    labels = [day.isoformat() for day in last_7_days]

    cooking_logs = fetch_cooking_logs_range(user_id, labels[0], labels[-1])
    recipes_map = {recipe["id"]: recipe for recipe in fetch_recipes()}

    recent_recipes = []
    seen_recipe_ids = set()
    for log in sorted(cooking_logs, key=lambda x: x["cooked_at_date"], reverse=True):
        recipe = recipes_map.get(log["recipe_id"])
        if recipe and log["recipe_id"] not in seen_recipe_ids:
            recent_recipes.append({
                "id": recipe["id"],
                "title": recipe["title"],
                "cooked_at_date": log["cooked_at_date"],
            })
            seen_recipe_ids.add(log["recipe_id"])
            if len(recent_recipes) >= 3:
                break

    return render_template(
        "dashboard.html",
        user=current_user(),
        recognition_count=recognition_count,
        recipe_count=recipe_count,
        expiry_alert_count=len(expiry_alerts),
        recognition_logs=recognition_logs,
        recent_recipes=recent_recipes,
    )


def _mock_recognize(filename: str) -> List[Dict[str, str]]:
    pool = ["鶏むね肉", "卵", "ブロッコリー", "牛乳", "ご飯", "豆腐", "トマト", "玉ねぎ"]
    matches = []
    name = filename.lower()
    keyword_map = {
        "chicken": "鶏むね肉",
        "egg": "卵",
        "broccoli": "ブロッコリー",
        "milk": "牛乳",
        "rice": "ご飯",
        "tofu": "豆腐",
        "tomato": "トマト",
        "onion": "玉ねぎ",
    }
    for key, value in keyword_map.items():
        if key in name and value not in matches:
            matches.append(value)

    if not matches:
        matches = random.sample(pool, random.randint(3, 6))

    results = []
    for item in matches:
        results.append({
            "name": item,
            "quantity": random.randint(1, 3),
            "unit": "個" if item in ["卵", "トマト"] else "枚" if item == "鶏むね肉" else "株" if item == "ブロッコリー" else "本" if item == "牛乳" else "杯" if item == "ご飯" else "丁" if item == "豆腐" else "個",
        })
    return results


@app.get("/recognize")
@login_required
def recognize():
    items = session.get("recognize_items", [])
    return render_template("recognize.html", items=items, user=current_user())


@app.post("/recognize")
@login_required
def recognize_post():
    file = request.files.get("image")
    if not file:
        return redirect(url_for("recognize"))

    results = _mock_recognize(file.filename or "")
    session["recognize_items"] = results
    session.modified = True
    return redirect(url_for("recognize"))


@app.post("/recognize/update/<int:item_index>")
@login_required
def recognize_update(item_index: int):
    items = session.get("recognize_items", [])
    if 0 <= item_index < len(items):
        name = request.form.get("name", "").strip()
        quantity = request.form.get("quantity", "1").strip()
        unit = request.form.get("unit", "").strip()
        if name and quantity.isdigit() and unit:
            items[item_index] = {
                "name": name,
                "quantity": int(quantity),
                "unit": unit,
            }
            session["recognize_items"] = items
            session.modified = True
    return redirect(url_for("recognize"))


@app.post("/recognize/delete/<int:item_index>")
@login_required
def recognize_delete(item_index: int):
    items = session.get("recognize_items", [])
    if 0 <= item_index < len(items):
        items.pop(item_index)
        session["recognize_items"] = items
        session.modified = True
    return redirect(url_for("recognize"))


@app.post("/recognize/save")
@login_required
def recognize_save():
    items = session.get("recognize_items", [])
    user_id = session["user_id"]
    for item in items:
        upsert_pantry_item(
            user_id,
            item["name"],
            int(item["quantity"]),
            item["unit"],
            date.today().isoformat(),
        )
    if items:
        add_recognition_log(user_id, datetime.now().isoformat(), len(items))
    session["recognize_items"] = []
    session.modified = True
    return redirect(url_for("pantry"))


@app.get("/pantry")
@login_required
def pantry():
    user_id = session["user_id"]
    items = fetch_pantry_items(user_id)
    expiry_alerts = fetch_expiry_alerts(user_id)
    return render_template("pantry.html", items=items, expiry_alert_count=len(expiry_alerts), user=current_user())


@app.post("/pantry/add")
@login_required
def pantry_add():
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()
    expiry_date = request.form.get("expiry_date", "").strip()
    expiry_value = expiry_date or None
    if name and quantity_raw.isdigit() and unit:
        upsert_pantry_item(
            session["user_id"],
            name,
            int(quantity_raw),
            unit,
            expiry_value,
        )
    return redirect(url_for("pantry"))


@app.get("/vision")
@login_required
def vision():
    demo_catalog = _build_demo_catalog()
    return render_template("vision.html", user=current_user(), demo_catalog=demo_catalog)


@app.post("/api/vision/ingredients")
@login_required
def vision_ingredients():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "missing_image"}), 400

    image_bytes = file.read()
    if not image_bytes:
        return jsonify({"error": "empty_image"}), 400

    mime_type = file.mimetype or "image/jpeg"
    prefer_cache = request.headers.get("X-Demo-Image") == "1"
    cache_path = _demo_cache_path(image_bytes)
    cached_ingredients = _read_demo_cache(cache_path)

    if prefer_cache and cached_ingredients is not None:
        response = jsonify({"ingredients": cached_ingredients})
        response.headers["X-Cache-Status"] = "Cached"
        return response

    try:
        ingredients = recognize_ingredients_from_bytes(image_bytes, mime_type)
    except MissingAPIKeyError as exc:
        if cached_ingredients is not None:
            response = jsonify({"ingredients": cached_ingredients})
            response.headers["X-Cache-Status"] = "Cached"
            response.headers["X-Cache-Fallback"] = "1"
            return response
        return jsonify({"error": "missing_api_key", "detail": str(exc)}), 500
    except VisionTimeoutError as exc:
        if cached_ingredients is not None:
            response = jsonify({"ingredients": cached_ingredients})
            response.headers["X-Cache-Status"] = "Cached"
            response.headers["X-Cache-Fallback"] = "1"
            return response
        return jsonify({"error": "timeout", "detail": str(exc)}), 504
    except NonJsonResponseError as exc:
        if cached_ingredients is not None:
            response = jsonify({"ingredients": cached_ingredients})
            response.headers["X-Cache-Status"] = "Cached"
            response.headers["X-Cache-Fallback"] = "1"
            return response
        return jsonify({"error": "non_json_response", "detail": str(exc)}), 502
    except OpenAIVisionError as exc:
        if cached_ingredients is not None:
            response = jsonify({"ingredients": cached_ingredients})
            response.headers["X-Cache-Status"] = "Cached"
            response.headers["X-Cache-Fallback"] = "1"
            return response
        return jsonify({"error": "vision_error", "detail": str(exc)}), 502
    except Exception:
        if cached_ingredients is not None:
            response = jsonify({"ingredients": cached_ingredients})
            response.headers["X-Cache-Status"] = "Cached"
            response.headers["X-Cache-Fallback"] = "1"
            return response
        return jsonify({"error": "unknown_error"}), 500

    if ingredients:
        _write_demo_cache(cache_path, ingredients)

    response = jsonify({"ingredients": ingredients})
    response.headers["X-Cache-Status"] = "Live"
    return response


@app.post("/api/vision/save")
@login_required
def vision_save():
    payload = request.get_json(silent=True) or {}
    items = payload.get("ingredients", [])
    if not isinstance(items, list):
        return jsonify({"error": "invalid_payload"}), 400

    user_id = session["user_id"]
    saved = 0
    today_str = date.today().isoformat()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        quantity_raw = item.get("quantity", 1)
        try:
            quantity = int(float(quantity_raw))
        except (TypeError, ValueError):
            quantity = 1
        unit = str(item.get("unit", "個")).strip() or "個"
        expiry_date = str(item.get("expiry_date", "")).strip() or today_str
        upsert_pantry_item(user_id, name, quantity, unit, expiry_date)
        saved += 1

    return jsonify({"saved": saved})


@app.post("/pantry/update/<int:item_id>")
@login_required
def pantry_update(item_id: int):
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()
    expiry_date = request.form.get("expiry_date", "").strip()
    expiry_value = expiry_date or None
    if name and quantity_raw.isdigit() and unit:
        update_pantry_item(
            session["user_id"],
            item_id,
            name,
            int(quantity_raw),
            unit,
            expiry_value,
        )
    return redirect(url_for("pantry"))


@app.get("/pantry/delete/<int:item_id>")
@login_required
def pantry_delete(item_id: int):
    delete_pantry_item(session["user_id"], item_id)
    return redirect(url_for("pantry"))


@app.get("/recipes")
@login_required
def recipes():
    pantry_items = fetch_pantry_items(session["user_id"])
    pantry_names = {item["name"] for item in pantry_items}
    recipes_data = []
    for recipe in fetch_recipes_with_ingredients():
        ingredients = recipe.get("ingredients") or []
        if not ingredients:
            ingredients = json.loads(recipe["ingredients_json"])

        required = [ing for ing in ingredients if ing.get("role") == "required"]
        if not required:
            required = ingredients
        required_names = {ing["name"] for ing in required}
        matched_required = [ing for ing in required if ing["name"] in pantry_names]

        total_required = max(1, len(required_names))
        match_rate = len(matched_required) / total_required
        missing_required = total_required - len(matched_required)

        if match_rate < 0.6 and missing_required > 2:
            continue

        nutrition = json.loads(recipe["nutrition_json"])
        health_score = 0
        if nutrition.get("protein", 0) >= 30:
            health_score += 10
        if nutrition.get("veg_score", 0) >= 2:
            health_score += 10
        if nutrition.get("kcal", 0) <= 500:
            health_score += 10
        if nutrition.get("fat", 0) <= 15:
            health_score += 10
        if nutrition.get("carb", 0) >= 70:
            health_score -= 10
        health_score = max(0, min(40, health_score))

        match_score = max(0, min(60, int(match_rate * 60) - missing_required * 8))
        total_score = match_score + health_score

        if total_score >= 85:
            grade = "A"
        elif total_score >= 70:
            grade = "B"
        elif total_score >= 55:
            grade = "C"
        else:
            grade = "D"

        recipes_data.append(
            {
                **recipe,
                "match_count": len(matched_required),
                "match_items": matched_required,
                "match_rate": int(match_rate * 100),
                "missing_required": missing_required,
                "health_score": health_score,
                "total_score": total_score,
                "grade": grade,
            }
        )
    recipes_data.sort(key=lambda r: r["total_score"], reverse=True)
    recipes_data = recipes_data[:15]
    return render_template("recipes.html", recipes=recipes_data, user=current_user())


@app.get("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()
    results = []

    if query:
        results = search_recipes(query)
        # 计算每个菜谱的匹配度（基于食材）
        for recipe in results:
            try:
                ingredients = json.loads(recipe.get("ingredients_json", "[]"))
                recipe["ingredients"] = ingredients
            except (json.JSONDecodeError, TypeError):
                recipe["ingredients"] = []

    return render_template(
        "search.html",
        query=query,
        results=results,
        user=current_user(),
    )


@app.get("/recipes/<int:recipe_id>")
@login_required
def recipe_detail(recipe_id: int):
    recipe = fetch_recipe_by_id(recipe_id)
    if not recipe:
        return redirect(url_for("recipes"))

    # Calculate match rate with pantry items
    user_id = session["user_id"]
    pantry_items = fetch_pantry_items(user_id)
    pantry_names = {item["name"] for item in pantry_items}
    ingredients = json.loads(recipe["ingredients_json"])
    matched_ingredients = [ing for ing in ingredients if ing["name"] in pantry_names]
    match_rate = int((len(matched_ingredients) / len(ingredients) * 100) if ingredients else 0)

    nutrition_data = json.loads(recipe["nutrition_json"])

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        ingredients=ingredients,
        steps=json.loads(recipe["steps_json"]),
        nutrition=nutrition_data,
        match_rate=match_rate,
        matched_count=len(matched_ingredients),
        total_ingredients=len(ingredients),
        user=current_user(),
    )


@app.post("/recipes/<int:recipe_id>/cook")
@login_required
def recipe_cook(recipe_id: int):
    add_cooking_log(session["user_id"], recipe_id, date.today().isoformat())
    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


def _nutrition_score(today_totals: Dict[str, float]) -> Dict[str, str]:
    total_kcal = today_totals.get("kcal", 0)
    protein = today_totals.get("protein", 0)
    veg_score = today_totals.get("veg_score", 0)

    score = 50
    if total_kcal == 0:
        score = 20
    elif 1600 <= total_kcal <= 2400:
        score += 20
    elif total_kcal < 1400 or total_kcal > 2600:
        score -= 5

    if protein >= 60:
        score += 20
    elif protein >= 40:
        score += 10
    else:
        score -= 5

    if veg_score >= 2:
        score += 10

    score = max(0, min(100, int(score)))

    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    else:
        grade = "D"

    reasons = []
    if total_kcal == 0:
        reasons.append("本日の食事記録がありません")
    elif total_kcal < 1400:
        reasons.append("カロリーが少なめです")
    elif total_kcal > 2600:
        reasons.append("カロリーが高めです")
    else:
        reasons.append("カロリーは適正範囲です")

    if protein < 40:
        reasons.append("たんぱく質が不足気味です")
    else:
        reasons.append("たんぱく質が十分です")

    if veg_score < 2:
        reasons.append("野菜スコアを上げましょう")
    else:
        reasons.append("野菜摂取は良好です")

    return {"score": score, "grade": grade, "reasons": reasons[:3]}


@app.get("/nutrition")
@login_required
def nutrition():
    recipes_map = {recipe["id"]: recipe for recipe in fetch_recipes()}

    today = date.today()
    last_7_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    labels = [day.isoformat() for day in last_7_days]

    daily_totals = {label: {"kcal": 0, "protein": 0} for label in labels}
    today_totals = {"kcal": 0, "protein": 0, "veg_score": 0}

    logs = fetch_cooking_logs_range(
        session["user_id"], labels[0], labels[-1]
    )

    for log in logs:
        recipe = recipes_map.get(log["recipe_id"])
        if not recipe:
            continue
        nutrition = json.loads(recipe["nutrition_json"])
        day_key = log["cooked_at_date"]
        if day_key in daily_totals:
            daily_totals[day_key]["kcal"] += nutrition.get("kcal", 0)
            daily_totals[day_key]["protein"] += nutrition.get("protein", 0)
        if day_key == today.isoformat():
            today_totals["kcal"] += nutrition.get("kcal", 0)
            today_totals["protein"] += nutrition.get("protein", 0)
            today_totals["veg_score"] += nutrition.get("veg_score", 0)

    score_data = _nutrition_score(today_totals)
    kcal_series = [daily_totals[label]["kcal"] for label in labels]
    protein_series = [daily_totals[label]["protein"] for label in labels]

    alerts = []
    if today_totals["protein"] < 40:
        alerts.append("たんぱく質を強化しましょう")
    if today_totals["veg_score"] < 2:
        alerts.append("野菜摂取が不足しています")
    if not alerts:
        alerts.append("栄養バランスは良好です")

    pantry_items = fetch_pantry_items(session["user_id"])
    pantry_names = {item["name"] for item in pantry_items}
    shopping_list = []
    if today_totals["protein"] < 40:
        for item in ["鶏むね肉", "豆腐", "牛乳"]:
            if item not in pantry_names:
                shopping_list.append(item)
    if today_totals["veg_score"] < 2:
        for item in ["ブロッコリー", "トマト", "玉ねぎ"]:
            if item not in pantry_names:
                shopping_list.append(item)
    if not shopping_list:
        shopping_list = ["牛乳", "卵"]

    return render_template(
        "nutrition.html",
        user=current_user(),
        score_data=score_data,
        labels=labels,
        kcal_series=kcal_series,
        protein_series=protein_series,
        alerts=alerts,
        shopping_list=shopping_list,
        today_totals=today_totals,
    )


@app.get("/notifications")
@login_required
def notifications():
    user_id = session["user_id"]
    expiry_alerts = fetch_expiry_alerts(user_id)
    return render_template(
        "notifications.html",
        user=current_user(),
        alerts=expiry_alerts,
        alert_count=len(expiry_alerts),
    )


if __name__ == "__main__":
    app.run(debug=True)

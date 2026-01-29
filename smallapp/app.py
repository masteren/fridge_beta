import json
import os
import random
from datetime import date, timedelta
from functools import wraps
from typing import Dict, List

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import (
    add_cooking_log,
    create_user,
    fetch_pantry_items,
    fetch_recipe_by_id,
    fetch_recipes,
    get_user_by_id,
    get_user_by_username,
    init_db,
    seed_data,
    upsert_pantry_item,
    update_pantry_item,
    delete_pantry_item,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


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


@app.get("/")
def home():
    return render_template("home.html", user=current_user())


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
    return render_template("dashboard.html", user=current_user())


def _mock_recognize(filename: str) -> List[Dict[str, str]]:
    pool = ["鸡胸肉", "鸡蛋", "西兰花", "牛奶", "米饭", "番茄", "洋葱", "豆腐"]
    matches = []
    name = filename.lower()
    keyword_map = {
        "chicken": "鸡胸肉",
        "egg": "鸡蛋",
        "broccoli": "西兰花",
        "milk": "牛奶",
        "rice": "米饭",
        "tomato": "番茄",
        "onion": "洋葱",
        "tofu": "豆腐",
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
            "unit": "份",
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
        )
    session["recognize_items"] = []
    session.modified = True
    return redirect(url_for("pantry"))


@app.get("/pantry")
@login_required
def pantry():
    items = fetch_pantry_items(session["user_id"])
    return render_template("pantry.html", items=items, user=current_user())


@app.post("/pantry/add")
@login_required
def pantry_add():
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()
    if name and quantity_raw.isdigit() and unit:
        upsert_pantry_item(session["user_id"], name, int(quantity_raw), unit)
    return redirect(url_for("pantry"))


@app.post("/pantry/update/<int:item_id>")
@login_required
def pantry_update(item_id: int):
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()
    if name and quantity_raw.isdigit() and unit:
        update_pantry_item(session["user_id"], item_id, name, int(quantity_raw), unit)
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
    for recipe in fetch_recipes():
        ingredients = json.loads(recipe["ingredients_json"])
        match = [ing for ing in ingredients if ing["name"] in pantry_names]
        recipes_data.append(
            {
                **recipe,
                "match_count": len(match),
                "match_items": match,
            }
        )
    recipes_data.sort(key=lambda r: r["match_count"], reverse=True)
    return render_template("recipes.html", recipes=recipes_data, user=current_user())


@app.get("/recipes/<int:recipe_id>")
@login_required
def recipe_detail(recipe_id: int):
    recipe = fetch_recipe_by_id(recipe_id)
    if not recipe:
        return redirect(url_for("recipes"))
    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        ingredients=json.loads(recipe["ingredients_json"]),
        steps=json.loads(recipe["steps_json"]),
        nutrition=json.loads(recipe["nutrition_json"]),
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

    from db import fetch_cooking_logs_range

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
        for item in ["鸡胸肉", "豆腐", "牛奶"]:
            if item not in pantry_names:
                shopping_list.append(item)
    if today_totals["veg_score"] < 2:
        for item in ["西兰花", "番茄", "洋葱"]:
            if item not in pantry_names:
                shopping_list.append(item)
    if not shopping_list:
        shopping_list = ["牛奶", "鸡蛋"]

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


if __name__ == "__main__":
    app.run(debug=True)

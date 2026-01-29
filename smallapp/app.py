from flask import Flask, redirect, render_template, request, url_for

from db import add_ingredient, delete_ingredient, fetch_ingredients, init_db

app = Flask(__name__)


@app.before_request
def ensure_db() -> None:
    init_db()


@app.get("/ingredients")
def ingredients_list():
    ingredients = fetch_ingredients()
    return render_template("ingredients.html", ingredients=ingredients)


@app.post("/add")
def add():
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "").strip()
    unit = request.form.get("unit", "").strip()

    if name and quantity_raw.isdigit() and unit:
        add_ingredient(name, int(quantity_raw), unit)

    return redirect(url_for("ingredients_list"))


@app.get("/delete/<int:item_id>")
def delete(item_id: int):
    delete_ingredient(item_id)
    return redirect(url_for("ingredients_list"))


if __name__ == "__main__":
    app.run(debug=True)

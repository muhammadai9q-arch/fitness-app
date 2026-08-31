  import sqlite3
import os
from datetime import date
from flask import Flask, request, jsonify, g, send_from_directory
from seed_foods import FOODS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
FRONTEND_DIR = BASE_DIR

app = Flask(__name__, static_folder=None)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    fresh = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calories REAL NOT NULL,
            protein REAL NOT NULL,
            carbs REAL NOT NULL,
            fat REAL NOT NULL,
            serving_grams REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER,
            custom_name TEXT,
            grams REAL NOT NULL,
            calories REAL NOT NULL,
            protein REAL NOT NULL,
            carbs REAL NOT NULL,
            fat REAL NOT NULL,
            entry_date TEXT NOT NULL,
            FOREIGN KEY (food_id) REFERENCES foods (id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            weight_kg REAL, height_cm REAL, age INTEGER,
            gender TEXT, activity TEXT, goal TEXT,
            target_calories REAL, target_protein REAL,
            target_carbs REAL, target_fat REAL
        )
    """)
    conn.commit()
    if fresh:
        cur.executemany(
            "INSERT INTO foods (name, calories, protein, carbs, fat, serving_grams) VALUES (?, ?, ?, ?, ?, ?)",
            FOODS,
        )
        conn.commit()
    conn.close()


@app.route("/api/foods")
def search_foods():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT * FROM foods WHERE name LIKE ? ORDER BY name LIMIT 30",
            (f"%{q}%",),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM foods ORDER BY name LIMIT 30").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/log", methods=["GET"])
def get_log():
    d = request.args.get("date", date.today().isoformat())
    db = get_db()
    rows = db.execute(
        "SELECT * FROM log_entries WHERE entry_date = ? ORDER BY id DESC", (d,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/log", methods=["POST"])
def add_log():
    data = request.get_json()
    db = get_db()
    grams = float(data["grams"])
    entry_date = data.get("date", date.today().isoformat())

    if data.get("food_id"):
        food = db.execute("SELECT * FROM foods WHERE id = ?", (data["food_id"],)).fetchone()
        if not food:
            return jsonify({"error": "food not found"}), 404
        factor = grams / 100.0
        calories = food["calories"] * factor
        protein = food["protein"] * factor
        carbs = food["carbs"] * factor
        fat = food["fat"] * factor
        name = food["name"]
        food_id = food["id"]
    else:
        calories = float(data.get("calories", 0))
        protein = float(data.get("protein", 0))
        carbs = float(data.get("carbs", 0))
        fat = float(data.get("fat", 0))
        name = data.get("custom_name", "عنصر مخصص")
        food_id = None

    cur = db.execute(
        """INSERT INTO log_entries
           (food_id, custom_name, grams, calories, protein, carbs, fat, entry_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (food_id, name, grams, calories, protein, carbs, fat, entry_date),
    )
    db.commit()
    row = db.execute("SELECT * FROM log_entries WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/log/<int:entry_id>", methods=["DELETE"])
def delete_log(entry_id):
    db = get_db()
    db.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))
    db.commit()
    return "", 204


@app.route("/api/summary")
def summary():
    d = request.args.get("date", date.today().isoformat())
    db = get_db()
    row = db.execute(
        """SELECT COALESCE(SUM(calories),0) c, COALESCE(SUM(protein),0) p,
                  COALESCE(SUM(carbs),0) cb, COALESCE(SUM(fat),0) f
           FROM log_entries WHERE entry_date = ?""",
        (d,),
    ).fetchone()
    prof = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return jsonify({
        "totals": {"calories": row["c"], "protein": row["p"], "carbs": row["cb"], "fat": row["f"]},
        "targets": dict(prof) if prof else None,
    })


@app.route("/api/profile", methods=["GET"])
def get_profile():
    db = get_db()
    row = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return jsonify(dict(row) if row else None)


@app.route("/api/profile", methods=["POST"])
def set_profile():
    data = request.get_json()
    weight = float(data["weight_kg"])
    height = float(data["height_cm"])
    age = int(data["age"])
    gender = data["gender"]  # 'male' or 'female'
    activity = data["activity"]  # sedentary/light/moderate/active/very_active
    goal = data["goal"]  # lose/maintain/gain

    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    activity_factors = {
        "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
        "active": 1.725, "very_active": 1.9,
    }
    tdee = bmr * activity_factors.get(activity, 1.2)

    if goal == "lose":
        target_calories = tdee - 500
    elif goal == "gain":
        target_calories = tdee + 300
    else:
        target_calories = tdee

    target_protein = weight * (2.0 if goal == "gain" else 1.8)
    target_fat = (target_calories * 0.25) / 9
    target_carbs = (target_calories - (target_protein * 4) - (target_fat * 9)) / 4

    db = get_db()
    db.execute(
        """INSERT INTO profile (id, weight_kg, height_cm, age, gender, activity, goal,
                                 target_calories, target_protein, target_carbs, target_fat)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             weight_kg=excluded.weight_kg, height_cm=excluded.height_cm, age=excluded.age,
             gender=excluded.gender, activity=excluded.activity, goal=excluded.goal,
             target_calories=excluded.target_calories, target_protein=excluded.target_protein,
             target_carbs=excluded.target_carbs, target_fat=excluded.target_fat""",
        (weight, height, age, gender, activity, goal,
         target_calories, target_protein, target_carbs, target_fat),
    )
    db.commit()
    row = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return jsonify(dict(row))


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    # When run under gunicorn (cloud hosting), init the DB at import time.
    init_db()   


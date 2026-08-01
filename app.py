import os
import json
import base64
import secrets
import requests  # <-- ADDED
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
from jinja2 import Template

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not set. AI features will fall back to manual entry.")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TEXT_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.6-27b"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hydroshield.db"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

db = SQLAlchemy(app)

SOIL_TYPES = {
    "sandy":  "Sandy — drains fast, dries out quickly",
    "clay":   "Clay / muddy — holds water, drains slowly",
    "loamy":  "Loamy — balanced, holds moisture well",
    "silty":  "Silty — smooth, holds moisture, can compact",
    "rocky":  "Rocky / stony — drains very fast",
    "chalky": "Chalky — drains fast, alkaline",
    "peaty":  "Peaty — dark, holds a lot of moisture",
}

DEFAULT_MATURITY_DAYS = 75
DEFAULT_MOISTURE_LOW = 30
DEFAULT_MOISTURE_HIGH = 70

PLANT_DB = {
    "tunisian tomatoes": {"label": "Tunisian Tomatoes", "maturity_days": 80, "moisture_low": 30, "moisture_high": 70},
    "roma tomatoes": {"label": "Roma Tomatoes", "maturity_days": 75, "moisture_low": 30, "moisture_high": 70},
    "tomato": {"label": "Tomatoes", "maturity_days": 75, "moisture_low": 30, "moisture_high": 70},
    "cherry tomato": {"label": "Cherry Tomatoes", "maturity_days": 65, "moisture_low": 30, "moisture_high": 65},
    "cucumber": {"label": "Cucumbers", "maturity_days": 55, "moisture_low": 40, "moisture_high": 75},
    "romaine lettuce": {"label": "Romaine Lettuce", "maturity_days": 65, "moisture_low": 45, "moisture_high": 80},
    "lettuce": {"label": "Lettuce", "maturity_days": 55, "moisture_low": 45, "moisture_high": 80},
    "pepper": {"label": "Peppers", "maturity_days": 70, "moisture_low": 30, "moisture_high": 65},
    "bell pepper": {"label": "Bell Peppers", "maturity_days": 75, "moisture_low": 30, "moisture_high": 65},
    "watermelon": {"label": "Watermelon", "maturity_days": 90, "moisture_low": 25, "moisture_high": 60},
    "melon": {"label": "Melon", "maturity_days": 85, "moisture_low": 25, "moisture_high": 60},
    "eggplant": {"label": "Eggplant", "maturity_days": 80, "moisture_low": 30, "moisture_high": 65},
    "zucchini": {"label": "Zucchini / Courgette", "maturity_days": 50, "moisture_low": 35, "moisture_high": 70},
    "squash": {"label": "Squash", "maturity_days": 70, "moisture_low": 30, "moisture_high": 65},
    "pumpkin": {"label": "Pumpkin", "maturity_days": 100, "moisture_low": 30, "moisture_high": 65},
    "onion": {"label": "Onion", "maturity_days": 100, "moisture_low": 25, "moisture_high": 55},
    "garlic": {"label": "Garlic", "maturity_days": 150, "moisture_low": 20, "moisture_high": 50},
    "potato": {"label": "Potato", "maturity_days": 90, "moisture_low": 30, "moisture_high": 65},
    "carrot": {"label": "Carrot", "maturity_days": 75, "moisture_low": 25, "moisture_high": 60},
    "cabbage": {"label": "Cabbage", "maturity_days": 80, "moisture_low": 35, "moisture_high": 70},
    "cauliflower": {"label": "Cauliflower", "maturity_days": 75, "moisture_low": 35, "moisture_high": 70},
    "broccoli": {"label": "Broccoli", "maturity_days": 70, "moisture_low": 35, "moisture_high": 70},
    "spinach": {"label": "Spinach", "maturity_days": 40, "moisture_low": 40, "moisture_high": 75},
    "chard": {"label": "Swiss Chard", "maturity_days": 55, "moisture_low": 35, "moisture_high": 70},
    "green beans": {"label": "Green Beans", "maturity_days": 55, "moisture_low": 30, "moisture_high": 65},
    "peas": {"label": "Peas", "maturity_days": 60, "moisture_low": 30, "moisture_high": 65},
    "fava beans": {"label": "Fava Beans", "maturity_days": 90, "moisture_low": 25, "moisture_high": 60},
    "okra": {"label": "Okra", "maturity_days": 60, "moisture_low": 25, "moisture_high": 55},
    "radish": {"label": "Radish", "maturity_days": 28, "moisture_low": 35, "moisture_high": 70},
    "beet": {"label": "Beetroot", "maturity_days": 60, "moisture_low": 30, "moisture_high": 65},
    "turnip": {"label": "Turnip", "maturity_days": 50, "moisture_low": 30, "moisture_high": 65},
    "artichoke": {"label": "Artichoke", "maturity_days": 150, "moisture_low": 30, "moisture_high": 60},
    "olive tree": {"label": "Olive Tree", "maturity_days": 1825, "moisture_low": 15, "moisture_high": 40},
    "orange tree": {"label": "Orange Tree", "maturity_days": 1095, "moisture_low": 25, "moisture_high": 55},
    "lemon tree": {"label": "Lemon Tree", "maturity_days": 1095, "moisture_low": 25, "moisture_high": 55},
    "fig tree": {"label": "Fig Tree", "maturity_days": 1095, "moisture_low": 15, "moisture_high": 45},
    "grapevine": {"label": "Grapevine", "maturity_days": 1095, "moisture_low": 15, "moisture_high": 45},
    "pomegranate": {"label": "Pomegranate Tree", "maturity_days": 1095, "moisture_low": 15, "moisture_high": 45},
    "almond tree": {"label": "Almond Tree", "maturity_days": 1460, "moisture_low": 15, "moisture_high": 40},
    "apricot tree": {"label": "Apricot Tree", "maturity_days": 1095, "moisture_low": 20, "moisture_high": 50},
    "peach tree": {"label": "Peach Tree", "maturity_days": 1095, "moisture_low": 20, "moisture_high": 50},
    "strawberry": {"label": "Strawberry", "maturity_days": 90, "moisture_low": 35, "moisture_high": 70},
    "basil": {"label": "Basil", "maturity_days": 60, "moisture_low": 35, "moisture_high": 70},
    "mint": {"label": "Mint", "maturity_days": 60, "moisture_low": 40, "moisture_high": 75},
    "parsley": {"label": "Parsley", "maturity_days": 70, "moisture_low": 35, "moisture_high": 70},
    "coriander": {"label": "Coriander", "maturity_days": 45, "moisture_low": 35, "moisture_high": 70},
    "thyme": {"label": "Thyme", "maturity_days": 90, "moisture_low": 15, "moisture_high": 40},
    "rosemary": {"label": "Rosemary", "maturity_days": 90, "moisture_low": 15, "moisture_high": 40},
    "wheat": {"label": "Wheat", "maturity_days": 120, "moisture_low": 20, "moisture_high": 55},
    "barley": {"label": "Barley", "maturity_days": 100, "moisture_low": 20, "moisture_high": 55},
    "chickpea": {"label": "Chickpea", "maturity_days": 100, "moisture_low": 20, "moisture_high": 50},
    "lentil": {"label": "Lentil", "maturity_days": 100, "moisture_low": 20, "moisture_high": 50},
}

ICON_KEYWORDS = [
    ("tomat", "tomato"),
    ("cucumb", "cucumber"),
    ("lettuce", "lettuce"),
    ("romaine", "lettuce"),
    ("pepper", "pepper"),
    ("chili", "pepper"),
    ("watermelon", "watermelon"),
    ("melon", "watermelon"),
]

# ---------- Helper functions ----------
def icon_for(label):
    low = label.lower()
    for keyword, icon in ICON_KEYWORDS:
        if keyword in low:
            return icon
    return "leaf"

def growth_adjusted_thresholds(base_low, base_high, age_days, maturity_days):
    if not age_days or not maturity_days:
        return base_low, base_high
    fraction = age_days / maturity_days
    if fraction < 0.15:
        shift = -5
    elif fraction < 0.6:
        shift = 5
    elif fraction <= 1.0:
        shift = 0
    else:
        shift = -5
    low = max(10, min(90, base_low + shift))
    high = max(low + 10, min(95, base_high + shift))
    return low, high

def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None

def login_required_redirect():
    if not current_user():
        return redirect(url_for("welcome"))
    return None

# ---------- Vision call ----------
def call_vision_json(prompt_text, image_bytes, mime):
    if client is None:
        raise Exception("GROQ_API_KEY not configured")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        print("📸 Calling Groq vision with model:", VISION_MODEL)
        completion = client.chat.completions.create(
            model=VISION_MODEL,
            response_format={"type": "json_object"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
        )
        print("✅ Vision success")
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print("❌ Vision error:", e)
        if hasattr(e, 'response'):
            print("Response body:", e.response.text if hasattr(e.response, 'text') else "No body")
        raise

# ---------- Firebase fetch function ----------
FIREBASE_HOST = "https://test2708-2375b-default-rtdb.firebaseio.com"  # <-- YOUR FIREBASE URL

def fetch_firebase_data(device_id):
    """Fetch latest sensor data from Firebase for a given device_id."""
    if not device_id:
        return None
    url = f"{FIREBASE_HOST}/devices/{device_id}.json"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return data
    except Exception as e:
        print(f"[Firebase fetch] Error: {e}")
    return None

# ---------- Database Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    farm_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    fields = db.relationship("Field", backref="owner", cascade="all, delete-orphan")

class PlantKnowledge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False)
    maturity_days = db.Column(db.Integer, nullable=False)
    moisture_low = db.Column(db.Integer, nullable=False)
    moisture_high = db.Column(db.Integer, nullable=False)
    care_note = db.Column(db.String(300), nullable=True)
    source = db.Column(db.String(20), default="ai")

class Field(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    crop_label = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(20), default="leaf")

    crop_origin = db.Column(db.String(120), nullable=True)
    origin_source = db.Column(db.String(20), default="manual")

    area_hectares = db.Column(db.Float, nullable=True)

    estimated_age_days = db.Column(db.Integer, nullable=True)
    age_source = db.Column(db.String(20), default="manual")
    maturity_days = db.Column(db.Integer, nullable=True)

    health_status = db.Column(db.String(20), nullable=True)
    health_note = db.Column(db.String(300), nullable=True)
    health_source = db.Column(db.String(20), default="manual")

    soil_type = db.Column(db.String(20), nullable=True)
    soil_source = db.Column(db.String(20), default="manual")

    moisture_low = db.Column(db.Integer, default=DEFAULT_MOISTURE_LOW)
    moisture_high = db.Column(db.Integer, default=DEFAULT_MOISTURE_HIGH)

    irrigation_on = db.Column(db.Boolean, default=False)
    auto_mode = db.Column(db.Boolean, default=True)

    last_moisture = db.Column(db.Float, nullable=True)
    last_temperature = db.Column(db.Float, nullable=True)
    last_rain = db.Column(db.Boolean, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)

    sensor_token = db.Column(db.String(64), unique=True, default=lambda: secrets.token_hex(16))
    device_id = db.Column(db.String(64), unique=True, nullable=True)  # <-- NEW

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "crop_label": self.crop_label,
            "icon": self.icon,
            "crop_origin": self.crop_origin,
            "origin_source": self.origin_source,
            "area_hectares": self.area_hectares,
            "estimated_age_days": self.estimated_age_days,
            "age_source": self.age_source,
            "maturity_days": self.maturity_days,
            "health_status": self.health_status,
            "health_note": self.health_note,
            "health_source": self.health_source,
            "soil_type": self.soil_type,
            "soil_label": SOIL_TYPES.get(self.soil_type),
            "soil_source": self.soil_source,
            "moisture_low": self.moisture_low,
            "moisture_high": self.moisture_high,
            "irrigation_on": self.irrigation_on,
            "auto_mode": self.auto_mode,
            "last_moisture": self.last_moisture,
            "last_temperature": self.last_temperature,
            "last_rain": self.last_rain,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "sensor_token": self.sensor_token,
            "device_id": self.device_id,
        }

with app.app_context():
    db.create_all()

# ---------- Plant knowledge ----------
def get_plant_knowledge(crop_label):
    key = crop_label.strip().lower()

    if key in PLANT_DB:
        p = PLANT_DB[key]
        return {"label": p["label"], "maturity_days": p["maturity_days"],
                "moisture_low": p["moisture_low"], "moisture_high": p["moisture_high"], "source": "builtin"}

    cached = PlantKnowledge.query.filter_by(name=key).first()
    if cached:
        return {"label": cached.label, "maturity_days": cached.maturity_days,
                "moisture_low": cached.moisture_low, "moisture_high": cached.moisture_high, "source": cached.source}

    if client is not None:
        try:
            completion = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": "You are an agronomy expert. Give realistic irrigation guidance for a named plant."},
                    {"role": "user", "content": (
                        f"Plant: {crop_label}. Give typical days to maturity from planting/transplant, "
                        "and a soil moisture percentage range (0-100) it should be kept in during its main "
                        "growing season, plus a one-sentence watering care note."
                    )},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "plant_knowledge",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "maturity_days": {"type": "integer"},
                                "moisture_low": {"type": "integer"},
                                "moisture_high": {"type": "integer"},
                                "care_note": {"type": "string"},
                            },
                            "required": ["maturity_days", "moisture_low", "moisture_high", "care_note"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
            data = json.loads(completion.choices[0].message.content)
            maturity_days = max(1, int(data["maturity_days"]))
            moisture_low = max(0, min(100, int(data["moisture_low"])))
            moisture_high = max(moisture_low + 5, min(100, int(data["moisture_high"])))
            care_note = str(data.get("care_note", ""))[:300]

            entry = PlantKnowledge(
                name=key, label=crop_label.strip(), maturity_days=maturity_days,
                moisture_low=moisture_low, moisture_high=moisture_high,
                care_note=care_note, source="ai",
            )
            db.session.add(entry)
            db.session.commit()
            return {"label": crop_label.strip(), "maturity_days": maturity_days,
                    "moisture_low": moisture_low, "moisture_high": moisture_high, "source": "ai"}
        except Exception:
            pass

    return {"label": crop_label.strip(), "maturity_days": DEFAULT_MATURITY_DAYS,
            "moisture_low": DEFAULT_MOISTURE_LOW, "moisture_high": DEFAULT_MOISTURE_HIGH, "source": "default"}

# ---------- Routes ----------
@app.route("/")
def welcome():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("welcome.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", error=None)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    farm_name = request.form.get("farm_name", "").strip()
    password = request.form.get("password", "")

    if not all([name, email, phone, password]):
        return render_template("signup.html", error="Please fill in every required field.")
    if User.query.filter_by(email=email).first():
        return render_template("signup.html", error="An account with that email already exists.")

    user = User(name=name, email=email, phone=phone, farm_name=farm_name or None,
                password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    session["user_id"] = user.id
    return redirect(url_for("setup"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return render_template("login.html", error="Incorrect email or password.")

    session["user_id"] = user.id
    return redirect(url_for("setup") if not user.fields else url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))

@app.route("/setup")
def setup():
    redirect_resp = login_required_redirect()
    if redirect_resp:
        return redirect_resp
    return render_template("setup.html", soils=SOIL_TYPES, user=current_user())

@app.route("/dashboard")
def dashboard():
    redirect_resp = login_required_redirect()
    if redirect_resp:
        return redirect_resp
    user = current_user()

    # ---------- NEW: Fetch data from Firebase for each field ----------
    for field in user.fields:
        if field.device_id:
            firebase_data = fetch_firebase_data(field.device_id)
            if firebase_data:
                updated = False
                if 'soil_moisture' in firebase_data:
                    field.last_moisture = firebase_data['soil_moisture']
                    updated = True
                if 'temperature' in firebase_data:
                    field.last_temperature = firebase_data['temperature']
                    updated = True
                if 'rain' in firebase_data:
                    field.last_rain = bool(firebase_data['rain'])
                    updated = True
                if updated:
                    field.last_seen = datetime.now(timezone.utc)
                    db.session.commit()

    return render_template("index.html", user=user, fields=user.fields, soils=SOIL_TYPES)

# ---------- API routes ----------
@app.route("/api/plants/suggest")
def suggest_plants():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify([])

    seen = set()
    results = []
    for key, p in PLANT_DB.items():
        if q in key or q in p["label"].lower():
            if p["label"] not in seen:
                seen.add(p["label"])
                results.append(p["label"])

    for row in PlantKnowledge.query.filter(PlantKnowledge.name.contains(q)).limit(10):
        if row.label not in seen:
            seen.add(row.label)
            results.append(row.label)

    return jsonify(results[:8])

@app.route("/api/fields", methods=["POST"])
def create_field():
    user = current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    data = request.form
    crop_label = data.get("crop_label", "").strip()
    if not crop_label:
        return jsonify({"error": "Tell us what plant is growing in this field."}), 400

    knowledge = get_plant_knowledge(crop_label)
    age_days = int(data["estimated_age_days"]) if data.get("estimated_age_days") else None
    moisture_low, moisture_high = growth_adjusted_thresholds(
        knowledge["moisture_low"], knowledge["moisture_high"], age_days, knowledge["maturity_days"]
    )

    soil_type = data.get("soil_type") or None
    if soil_type not in SOIL_TYPES:
        soil_type = None

    health_status = data.get("health_status") or None
    if health_status not in ("healthy", "possible_issue", "unclear"):
        health_status = None

    device_id = data.get("device_id", "").strip() or None

    field = Field(
        user_id=user.id,
        name=data.get("name", "").strip() or crop_label,
        crop_label=crop_label,
        icon=icon_for(crop_label),
        crop_origin=data.get("crop_origin", "").strip() or None,
        origin_source=data.get("origin_source", "manual"),
        area_hectares=float(data["area_hectares"]) if data.get("area_hectares") else None,
        estimated_age_days=age_days,
        age_source=data.get("age_source", "manual"),
        maturity_days=knowledge["maturity_days"],
        health_status=health_status,
        health_note=data.get("health_note", "").strip() or None,
        health_source=data.get("health_source", "manual"),
        soil_type=soil_type,
        soil_source=data.get("soil_source", "manual"),
        moisture_low=moisture_low,
        moisture_high=moisture_high,
        device_id=device_id,
    )
    db.session.add(field)
    db.session.commit()
    return jsonify(field.to_dict()), 201

@app.route("/api/fields/<int:field_id>", methods=["GET"])
def get_field(field_id):
    user = current_user()
    field = Field.query.get_or_404(field_id)
    if not user or field.user_id != user.id:
        return jsonify({"error": "Not authorized"}), 403
    return jsonify(field.to_dict())

@app.route("/api/fields/<int:field_id>", methods=["DELETE"])
def delete_field(field_id):
    user = current_user()
    field = Field.query.get_or_404(field_id)
    if not user or field.user_id != user.id:
        return jsonify({"error": "Not authorized"}), 403
    db.session.delete(field)
    db.session.commit()
    return jsonify({"deleted": field_id})

@app.route("/api/fields/<int:field_id>/irrigation", methods=["POST"])
def toggle_irrigation(field_id):
    user = current_user()
    field = Field.query.get_or_404(field_id)
    if not user or field.user_id != user.id:
        return jsonify({"error": "Not authorized"}), 403

    desired = request.json.get("on") if request.is_json else None
    field.irrigation_on = (not field.irrigation_on) if desired is None else bool(desired)
    field.auto_mode = False
    db.session.commit()
    return jsonify(field.to_dict())

@app.route("/api/fields/<int:field_id>/auto", methods=["POST"])
def set_auto_mode(field_id):
    user = current_user()
    field = Field.query.get_or_404(field_id)
    if not user or field.user_id != user.id:
        return jsonify({"error": "Not authorized"}), 403
    field.auto_mode = bool(request.json.get("auto", True))
    db.session.commit()
    return jsonify(field.to_dict())

@app.route("/api/analyze-photo", methods=["POST"])
def analyze_photo():
    crop_label = request.form.get("crop_label", "").strip() or "plant"
    photo = request.files.get("photo")
    if not photo:
        return jsonify({"error": "No photo received"}), 400

    if client is None:
        return jsonify({
            "estimated_age_days": None, "likely_origin": None,
            "health_status": None, "health_note": None,
            "note": "AI unavailable (no GROQ_API_KEY set on the server). Enter details manually.",
            "source": "unavailable",
        }), 200

    prompt = (
        f"This is a photo of a {crop_label} plant on a farm or garden. Respond ONLY with a JSON object "
        "with exactly these keys: "
        '"age_days" (integer estimate of the plant\'s age in days since germination/transplant, or null '
        'if you can\'t tell), "origin" (your best guess of the country or region this variety most likely '
        'originates from, or null if unclear), "health_status" (one of "healthy", "possible_issue", '
        '"unclear"), "health_note" (a short one-sentence note describing any visible sign of disease, '
        'pest damage, nutrient deficiency or stress if health_status is "possible_issue", otherwise an '
        'empty string).'
    )

    try:
        data = call_vision_json(prompt, photo.read(), photo.mimetype or "image/jpeg")
        age_days = data.get("age_days")
        age_days = int(age_days) if isinstance(age_days, (int, float)) else None
        origin = data.get("origin") or None
        if isinstance(origin, str) and origin.strip().lower() in ("unknown", "none", ""):
            origin = None
        health_status = data.get("health_status")
        if health_status not in ("healthy", "possible_issue", "unclear"):
            health_status = "unclear"
        health_note = (data.get("health_note") or "").strip() or None
    except Exception as exc:
        print("Exception in analyze_photo:", exc)
        return jsonify({
            "estimated_age_days": None, "likely_origin": None,
            "health_status": None, "health_note": None,
            "note": f"AI analysis failed ({exc.__class__.__name__}). Enter details manually.",
            "source": "error",
        }), 200

    return jsonify({
        "estimated_age_days": age_days,
        "likely_origin": origin,
        "health_status": health_status,
        "health_note": health_note,
        "note": "Estimated from the photo. Adjust anything that looks off.",
        "source": "ai_photo",
    })

@app.route("/api/estimate-soil", methods=["POST"])
def estimate_soil():
    photo = request.files.get("photo")
    if not photo:
        return jsonify({"error": "No photo received"}), 400

    if client is None:
        return jsonify({
            "soil_type": None,
            "note": "AI unavailable (no GROQ_API_KEY set on the server). Pick the soil type manually.",
            "source": "unavailable",
        }), 200

    options = ", ".join(SOIL_TYPES.keys())
    prompt = (
        "This is a close-up photo of farm or garden soil. Respond ONLY with a JSON object with exactly "
        f'these keys: "soil_type" (exactly one of: {options}) and "confidence" (one of "high", "medium", "low").'
    )

    try:
        data = call_vision_json(prompt, photo.read(), photo.mimetype or "image/jpeg")
        soil_type = data.get("soil_type")
        soil_type = soil_type if soil_type in SOIL_TYPES else None
    except Exception as exc:
        return jsonify({
            "soil_type": None,
            "note": f"AI analysis failed ({exc.__class__.__name__}). Pick the soil type manually.",
            "source": "error",
        }), 200

    if soil_type is None:
        return jsonify({
            "soil_type": None,
            "note": "Couldn't confidently classify that photo. Pick the soil type manually.",
            "source": "error",
        }), 200

    return jsonify({
        "soil_type": soil_type,
        "note": f"Looks like {SOIL_TYPES[soil_type].split(' — ')[0]} soil. Adjust it if that's off.",
        "source": "ai_photo",
    })

@app.route("/api/sensor/<token>/report", methods=["POST"])
def sensor_report(token):
    field = Field.query.filter_by(sensor_token=token).first()
    if not field:
        return jsonify({"error": "Unknown sensor token"}), 404

    data = request.get_json(force=True, silent=True) or {}
    field.last_moisture = data.get("moisture", field.last_moisture)
    field.last_temperature = data.get("temperature", field.last_temperature)
    field.last_rain = data.get("rain", field.last_rain)
    field.last_seen = datetime.now(timezone.utc)

    if field.auto_mode and field.last_moisture is not None:
        if field.last_rain:
            field.irrigation_on = False
        elif field.last_moisture <= field.moisture_low:
            field.irrigation_on = True
        elif field.last_moisture >= field.moisture_high:
            field.irrigation_on = False

    db.session.commit()
    return jsonify({"irrigate": field.irrigation_on})

@app.route("/api/sensor/<token>/command", methods=["GET"])
def sensor_command(token):
    field = Field.query.filter_by(sensor_token=token).first()
    if not field:
        return jsonify({"error": "Unknown sensor token"}), 404
    return jsonify({"irrigate": field.irrigation_on})

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    image_data_url = request.json.get("image", None)

    if client is None:
        return jsonify({"reply": "The assistant isn't configured yet (missing GROQ_API_KEY on the server)."})

    if image_data_url:
        try:
            header, encoded = image_data_url.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(encoded)

            if user_message.strip():
                prompt = (
                    f"The user sent a photo of a plant and asked: \"{user_message}\". "
                    "Analyze the image. If there are any visible problems (diseases, pests, "
                    "nutrient deficiencies, environmental stress), describe them clearly. "
                    "Also give practical, actionable advice to fix the issue. "
                    "If the plant looks healthy, just say it looks good."
                )
            else:
                prompt = (
                    "This is a photo of a plant. Detect any visible problems (diseases, pests, "
                    "nutrient deficiencies, environmental stress). Describe the symptoms and "
                    "give practical, actionable advice to fix them. "
                    "If it looks healthy, just say it looks good."
                )

            data = call_vision_json(prompt, image_bytes, mime_type)
            reply = data.get("analysis") or data.get("response") or data.get("message")
            if not reply:
                reply = json.dumps(data, indent=2)
            return jsonify({"reply": reply[:800]})

        except Exception as exc:
            return jsonify({"reply": f"Sorry, I couldn't analyze that photo. Error: {exc.__class__.__name__}. Please try again."})

    try:
        completion = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are the HydroShield assistant, a helpful expert on smart irrigation for small and "
                    "mid-size farms and gardens. You help users understand their field's soil moisture, "
                    "temperature and rain sensor readings, explain when and why irrigation starts or stops, "
                    "and give practical, concise growing and watering advice for any plant they ask about. "
                    "Keep answers short and practical."
                )},
                {"role": "user", "content": user_message},
            ],
        )
        reply = completion.choices[0].message.content
    except Exception as exc:
        reply = f"Sorry, the assistant hit an error ({exc.__class__.__name__}). Please try again."

    return jsonify({"reply": reply})

# ---------- Download Sketch (ESP8266 + Firebase) ----------
@app.route("/api/fields/<int:field_id>/sketch")
def download_sketch(field_id):
    user = current_user()
    field = Field.query.get_or_404(field_id)
    if not user or field.user_id != user.id:
        return jsonify({"error": "Not authorized"}), 403

    server_url = request.url_root.rstrip('/')
    token = field.sensor_token
    firebase_host = "https://test2708-2375b-default-rtdb.firebaseio.com"  # <-- YOUR FIREBASE URL

    sketch_template = """
/*
  HydroShield — ESP8266 field controller (Firebase only)
  Generated for field: {{ field_name }}
  Sensor token: {{ token }}
  Firebase: {{ firebase_host }}
*/

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <DHT.h>

// Wi‑Fi credentials
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Firebase endpoint
const char* FIREBASE_HOST = "{{ firebase_host }}";

// Device ID (generated automatically from chip ID)
String getDeviceId() {
  return "ESP_" + String(ESP.getChipId(), HEX);
}

// Pins (adjust to your wiring)
#define SOIL_PIN A0
#define RAIN_PIN D5
#define DHT_PIN  D4
#define RELAY_PIN D1
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

// Calibration values for soil moisture
const int SOIL_DRY_RAW = 780;
const int SOIL_WET_RAW = 320;

// Timing
const unsigned long REPORT_INTERVAL_MS = 30UL * 1000UL;
unsigned long lastReport = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RAIN_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  dht.begin();
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (millis() - lastReport >= REPORT_INTERVAL_MS) {
    lastReport = millis();
    float moisture = readSoilMoisture();
    float temperature = dht.readTemperature();
    bool rain = (digitalRead(RAIN_PIN) == LOW);
    sendToFirebase(moisture, temperature, rain);
  }
}

void connectWiFi() {
  Serial.printf("Connecting to Wi-Fi \"%s\"...\\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " Connected!" : " Failed.");
}

float readSoilMoisture() {
  int raw = analogRead(SOIL_PIN);
  raw = constrain(raw, SOIL_WET_RAW, SOIL_DRY_RAW);
  float pct = 100.0 * (float)(SOIL_DRY_RAW - raw) / (float)(SOIL_DRY_RAW - SOIL_WET_RAW);
  // Invert if your sensor gives opposite (uncomment next line)
  // pct = 100.0 - pct;
  return round(pct * 10) / 10.0;
}

void sendToFirebase(float moisture, float temperature, bool rain) {
  WiFiClientSecure secureClient;
  secureClient.setInsecure();
  HTTPClient http;
  String url = String(FIREBASE_HOST) + "/devices/" + getDeviceId() + ".json";
  String payload = "{";
  payload += "\"soil_moisture\":" + String(moisture, 1) + ",";
  payload += "\"temperature\":" + String(temperature, 1) + ",";
  payload += "\"rain\":" + String(rain ? 1 : 0);
  payload += "}";
  http.begin(secureClient, url);
  http.addHeader("Content-Type", "application/json");
  int httpCode = http.PATCH(payload);
  if (httpCode > 0) {
    Serial.printf("Firebase update OK (HTTP %d)\\n", httpCode);
  } else {
    Serial.printf("Firebase error: %s\\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}
"""

    template = Template(sketch_template)
    rendered = template.render(field_name=field.name, token=token, firebase_host=firebase_host)

    response = make_response(rendered)
    response.headers["Content-Disposition"] = f"attachment; filename=hydroshield_{field.name.replace(' ', '_')}.ino"
    response.headers["Content-Type"] = "text/plain"
    return response

# ---------- Run ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

import os
import json
import base64
import secrets
import requests  # <-- NEW
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
    # ... (your PLANT_DB as before, keep it)
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
FIREBASE_HOST = "https://test2708-2375b-default-rtdb.firebaseio.com"

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
    device_id = db.Column(db.String(64), unique=True, nullable=True)

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

# ---------- Create tables ----------
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
# ... (all your existing API routes: /api/plants/suggest, /api/fields, etc.)
# Keep everything from your original code – I'll include only the important ones for brevity.

# ---------- /api/device/report (optional, you can keep it but not needed) ----------
# If you want to keep the direct ESP reporting, you can keep the route; otherwise, you can remove it.

# ---------- Download Sketch (ESP8266 + Firebase) ----------
# This route generates a sketch that sends data to Firebase only, not to the website.
# That's perfect – the website reads from Firebase.

@app.route("/api/fields/<int:field_id>/sketch")
def download_sketch(field_id):
    user = current_user()
    field = Field.query.get_or_404(field_id)
    if not user or field.user_id != user.id:
        return jsonify({"error": "Not authorized"}), 403

    server_url = request.url_root.rstrip('/')
    token = field.sensor_token
    firebase_host = "https://test2708-2375b-default-rtdb.firebaseio.com"  # your Firebase URL

    sketch_template = """
// ... (your sketch template, with the Firebase host and token)
// The ESP will send data to Firebase, not to the website.
// The website will read from Firebase.
"""
    # (the full sketch is the same as before, but you can simplify it to only Firebase if you want)

    template = Template(sketch_template)
    rendered = template.render(field_name=field.name, token=token, server_url=server_url, firebase_host=firebase_host)

    response = make_response(rendered)
    response.headers["Content-Disposition"] = f"attachment; filename=hydroshield_{field.name.replace(' ', '_')}.ino"
    response.headers["Content-Type"] = "text/plain"
    return response

# ---------- Run ----------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

"""
HireLoop — Flask entry point
Run: python app.py
"""
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from db.models import init_db
from api.routes.candidates import candidates_bp, jd_bp
from api.routes.feedback import feedback_bp, model_bp

load_dotenv()

app = Flask(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
allowed_origins = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Blueprints ────────────────────────────────────────────────────────────────
app.register_blueprint(jd_bp,         url_prefix="/api/jd")
app.register_blueprint(candidates_bp, url_prefix="/api/candidates")
app.register_blueprint(feedback_bp,   url_prefix="/api/feedback")
app.register_blueprint(model_bp,      url_prefix="/api/model")


# ── Health ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "hireloop-api"})


@app.errorhandler(404)
def not_found(_err):
    return jsonify({"error": "Route not found", "path": request.path}), 404


@app.errorhandler(500)
def internal_error(_err):
    return jsonify({"error": "Internal server error"}), 500


# ── DB init on startup ────────────────────────────────────────────────────────
with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    print(f"[hireloop] Starting on port {port}, debug={debug}")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)

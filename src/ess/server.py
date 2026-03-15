import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify

from .viewer import get_viewer_html

# In-memory secret store: { id: { "ciphertext": str, "expires_at": datetime|None } }
_secrets: dict[str, dict] = {}
_lock = threading.Lock()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    @app.route("/s/<secret_id>")
    def viewer_page(secret_id):
        return get_viewer_html(), 200, {"Content-Type": "text/html"}

    @app.route("/api/secret/<secret_id>")
    def get_secret(secret_id):
        with _lock:
            entry = _secrets.pop(secret_id, None)

        if entry is None:
            return jsonify({"error": "not found"}), 404

        if entry["expires_at"] and datetime.now(timezone.utc) > entry["expires_at"]:
            return jsonify({"error": "expired", "expired": True}), 410

        print(f"\n\u2713 Secret {secret_id} viewed and deleted.")
        return jsonify({"ciphertext": entry["ciphertext"]})

    return app


def store_secret(secret_id: str, ciphertext: str, expires_at=None):
    with _lock:
        _secrets[secret_id] = {
            "ciphertext": ciphertext,
            "expires_at": expires_at,
        }


def _cleanup_expired():
    while True:
        time.sleep(60)
        now = datetime.now(timezone.utc)
        with _lock:
            expired = [
                sid for sid, entry in _secrets.items()
                if entry["expires_at"] and now > entry["expires_at"]
            ]
            for sid in expired:
                del _secrets[sid]
                print(f"\n\u23f1 Secret {sid} expired and deleted.")


def start_cleanup_thread():
    t = threading.Thread(target=_cleanup_expired, daemon=True)
    t.start()

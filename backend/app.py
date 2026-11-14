import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from .api.routes import api

def create_app():
    BASE_DIR = Path(__file__).resolve().parent
    FRONTEND_DIR = BASE_DIR.parent / "frontend"

    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(api, url_prefix="/api")

    @app.route("/", methods=["GET"])
    def serve_frontend():
        return send_from_directory(str(FRONTEND_DIR), "index.html")

    @app.route("/<path:path>", methods=["GET"])
    def serve_static(path):
        # serve frontend assets; fall back to index for SPA
        full = FRONTEND_DIR / path
        if full.exists() and full.is_file():
            return send_from_directory(str(FRONTEND_DIR), path)
        # check css/js subpaths
        return send_from_directory(str(FRONTEND_DIR), "index.html")

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500

    return app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app = create_app()
    debug = os.getenv("FLASK_ENV") == "development"
    print(f"IntelliTwin backend starting on http://0.0.0.0:{port}")
    print("Serving frontend from", Path(__file__).resolve().parent.parent / "frontend")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)

from flask import Flask

from .ai.ai_api import ai_bp
from .bottle.bottle_api import bottle_bp
from .config import Config
from .plane.plane_api import plane_bp
from .user.user_api import user_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.ensure_data_files()

    app.register_blueprint(user_bp, url_prefix="/api/users")
    app.register_blueprint(bottle_bp, url_prefix="/api/bottles")
    app.register_blueprint(plane_bp, url_prefix="/api/planes")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.get("/api/health")
    def health():
        return {"data": {"status": "ok"}}

    return app

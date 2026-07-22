from flask import Blueprint, jsonify, request

from app.services.content_service import moderate_locally, validate_content

ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/moderate")
def moderate():
    payload = request.get_json(silent=True) or {}
    error = validate_content(payload.get("content"))
    if error:
        return jsonify({"error": {"message": error}}), 400
    return jsonify({"data": moderate_locally(payload["content"].strip()), "provider": "local-fallback"})

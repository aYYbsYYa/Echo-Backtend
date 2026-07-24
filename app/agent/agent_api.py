from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from flask import Blueprint, current_app, jsonify, request

from app.services.agent_service import (
    AgentDemoError,
    get_soul_profile,
    match_soul_agents,
    run_agent_dialogue,
)


agent_bp = Blueprint("agent", __name__)
_rate_lock = Lock()
_rate_buckets: dict[str, dict[str, deque[float]]] = defaultdict(dict)


def _demo_user_id(value: object, default: str = "yeve") -> str:
    if not isinstance(value, str):
        return default
    return value.strip().lower() or default


def _payload() -> dict | None:
    value = request.get_json(silent=True)
    if value is None:
        return {}
    return value if isinstance(value, dict) else None


def _rate_limited(action: str, maximum: int, window_seconds: int = 60) -> bool:
    if current_app.config.get("TESTING"):
        return False
    client = request.remote_addr or "unknown"
    now = monotonic()
    with _rate_lock:
        bucket = _rate_buckets[action].setdefault(client, deque())
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()
        if len(bucket) >= maximum:
            return True
        bucket.append(now)
    return False


def _rate_limit_error():
    return jsonify({"error": {"message": "Soul Echo 请求太频繁，请稍后再试。"}}), 429


@agent_bp.get("/profile")
def soul_profile():
    if _rate_limited("profile", 10):
        return _rate_limit_error()
    user_id = _demo_user_id(request.args.get("user_id"))
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    try:
        profile = get_soul_profile(user_id, refresh=refresh)
    except AgentDemoError as error:
        return jsonify({"error": {"message": str(error)}}), 404
    return jsonify({"data": profile})


@agent_bp.post("/match")
def soul_match():
    if _rate_limited("match", 10):
        return _rate_limit_error()
    payload = _payload()
    if payload is None:
        return jsonify({"error": {"message": "请求体必须是 JSON 对象。"}}), 400
    user_id = _demo_user_id(payload.get("user_id"))
    try:
        limit = int(payload.get("limit", 3))
    except (TypeError, ValueError):
        return jsonify({"error": {"message": "limit 必须是 1 到 3 的整数。"}}), 400
    if not 1 <= limit <= 3:
        return jsonify({"error": {"message": "limit 必须是 1 到 3 的整数。"}}), 400

    try:
        result = match_soul_agents(user_id, limit=limit)
    except AgentDemoError as error:
        return jsonify({"error": {"message": str(error)}}), 404
    return jsonify({"data": result})


@agent_bp.post("/dialogue")
def soul_dialogue():
    if _rate_limited("dialogue", 5):
        return _rate_limit_error()
    payload = _payload()
    if payload is None:
        return jsonify({"error": {"message": "请求体必须是 JSON 对象。"}}), 400
    user_id = _demo_user_id(payload.get("user_id"))
    target = payload.get("target_user_id")
    target_user_id = _demo_user_id(target, "") if target is not None else None

    try:
        result = run_agent_dialogue(user_id, target_user_id)
    except AgentDemoError as error:
        return jsonify({"error": {"message": str(error)}}), 400
    return jsonify({"data": result}), 201

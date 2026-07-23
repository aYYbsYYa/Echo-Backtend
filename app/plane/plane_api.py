import random

from flask import Blueprint, jsonify, request

from app.services.ai_service import generate_developer_reply
from app.services.content_service import extract_tags, new_id, utc_now, validate_content
from app.storage import PlaneStorage, UserStorage

plane_bp = Blueprint("planes", __name__)
planes = PlaneStorage()
users = UserStorage()
SCENES = ("sky", "window", "tree")


def public_plane(item: dict, viewer_id: str | None = None) -> dict:
    author = users.find(item["user_id"]) or {}
    return {
        "id": item["id"],
        "content": item["content"],
        "nickname": author.get("nickname", "匿名旅人"),
        "avatar": author.get("avatar", "匿"),
        "region": item.get("region", "未标注"),
        "created_at": item["created_at"],
        "type": "plane",
        "scene": item["scene"],
        "views": item.get("views", 0),
        "reply": item.get("reply") if viewer_id == item["user_id"] else None,
        "is_author": viewer_id == item["user_id"],
    }


@plane_bp.post("")
def publish_plane():
    payload = request.get_json(silent=True) or {}
    error = validate_content(payload.get("content"))
    user = users.find(str(payload.get("user_id", "")))
    if error or not user:
        return jsonify({"error": {"message": error or "请先创建匿名身份。"}}), 400
    content = payload["content"].strip()
    item = {
        "id": new_id("plane", content),
        "content": content,
        "user_id": user["id"],
        "region": user["region"],
        "created_at": utc_now(),
        "tags": extract_tags(content),
        "scene": random.choice(SCENES),
        "views": 0,
        "reply": generate_developer_reply(user["nickname"], user["region"], content),
    }
    planes.append(item)
    return jsonify({"data": public_plane(item, user["id"])}), 201


@plane_bp.get("/discover")
def discover_plane():
    viewer_id = request.args.get("user_id", "")
    candidates = [item for item in planes.all() if item["user_id"] != viewer_id]
    if not candidates:
        return jsonify({"data": None, "message": "风里还没有新的纸飞机。"})
    item = random.choice(candidates)
    records = planes.all()
    for record in records:
        if record["id"] == item["id"]:
            record["views"] = record.get("views", 0) + 1
            item = record
            break
    planes.replace_all(records)
    return jsonify({"data": public_plane(item)})


@plane_bp.get("/<plane_id>")
def get_plane(plane_id: str):
    item = planes.find(plane_id)
    if not item:
        return jsonify({"error": {"message": "这架纸飞机已经飞远了。"}}), 404
    return jsonify({"data": public_plane(item, request.args.get("user_id"))})


@plane_bp.get("/mine/<user_id>")
def my_planes(user_id: str):
    own = [item for item in planes.all() if item["user_id"] == user_id]
    return jsonify({"data": [public_plane(item) for item in reversed(own)]})

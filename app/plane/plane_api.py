import random

from flask import Blueprint, jsonify, request

from app.services.ai_service import generate_developer_reply
from app.services.content_service import new_id, utc_now, validate_content
from app.storage.json_repository import JsonRepository
from app.config import Config
from app.storage import PlaneStorage, UserStorage

plane_bp = Blueprint("planes", __name__)
planes = PlaneStorage()
users = UserStorage()
likes = JsonRepository(Config.DATA_DIR / "likes.json")
comments = JsonRepository(Config.DATA_DIR / "comments.json")
SCENES = ("sky", "window", "tree")


def private_comments(plane_id: str) -> list[dict]:
    result = []
    for comment in comments.all():
        if comment.get("item_id") != plane_id:
            continue
        commenter = users.find(str(comment.get("user_id", ""))) or {}
        result.append(
            {
                **comment,
                "nickname": comment.get("nickname") or commenter.get("nickname", "匿名旅人"),
            }
        )
    return result


def public_plane(item: dict, viewer_id: str | None = None, include_private: bool = False) -> dict:
    author = users.find(item["user_id"]) or {}
    response = {
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
        "liked": any(
            like["item_id"] == item["id"] and like["user_id"] == viewer_id for like in likes.all()
        ),
    }
    if include_private or viewer_id == item["user_id"]:
        response["likes"] = sum(1 for like in likes.all() if like["item_id"] == item["id"])
        response["comments"] = private_comments(item["id"])
    return response


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
        "scene": random.choice(SCENES),
        "views": 0,
        "reply": generate_developer_reply(user["nickname"], user["region"], content),
    }
    planes.append(item)
    return jsonify({"data": public_plane(item, user["id"], True)}), 201


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
    return jsonify({"data": public_plane(item, viewer_id)})


@plane_bp.get("/<plane_id>")
def get_plane(plane_id: str):
    item = planes.find(plane_id)
    if not item:
        return jsonify({"error": {"message": "这架纸飞机已经飞远了。"}}), 404
    viewer_id = request.args.get("user_id")
    return jsonify({"data": public_plane(item, viewer_id)})


@plane_bp.post("/<plane_id>/likes")
def toggle_like(plane_id: str):
    item = planes.find(plane_id)
    payload = request.get_json(silent=True) or {}
    user_id = str(payload.get("user_id", ""))
    if not item or not users.find(user_id):
        return jsonify({"error": {"message": "无效的纸飞机或身份。"}}), 400
    records = likes.all()
    existing = next(
        (like for like in records if like["item_id"] == plane_id and like["user_id"] == user_id), None
    )
    if existing:
        records.remove(existing)
        liked = False
    else:
        records.append({"id": new_id("like", plane_id), "item_id": plane_id, "user_id": user_id})
        liked = True
    likes.replace_all(records)
    return jsonify({"data": {"liked": liked}})


@plane_bp.post("/<plane_id>/comments")
def create_comment(plane_id: str):
    item = planes.find(plane_id)
    payload = request.get_json(silent=True) or {}
    error = validate_content(payload.get("content"))
    user = users.find(str(payload.get("user_id", "")))
    if not item or error or not user:
        return jsonify({"error": {"message": error or "无效的纸飞机或身份。"}}), 400
    comments.append(
        {
            "id": new_id("comment", plane_id),
            "item_id": plane_id,
            "user_id": user["id"],
            "nickname": user["nickname"],
            "content": payload["content"].strip(),
            "created_at": utc_now(),
        }
    )
    return jsonify({"data": {"sent": True}}), 201


@plane_bp.get("/mine/<user_id>")
def my_planes(user_id: str):
    own = [item for item in planes.all() if item["user_id"] == user_id]
    return jsonify({"data": [public_plane(item, user_id, True) for item in reversed(own)]})

from flask import Blueprint, jsonify, request

from app.services.content_service import (
    extract_tags,
    generate_reply,
    moderate_locally,
    new_id,
    recommendation_score,
    utc_now,
    validate_content,
)
from app.storage import BottleStorage, UserStorage
from app.storage.json_repository import JsonRepository
from app.config import Config

bottle_bp = Blueprint("bottles", __name__)
bottles = BottleStorage()
users = UserStorage()
likes = JsonRepository(Config.DATA_DIR / "likes.json")
comments = JsonRepository(Config.DATA_DIR / "comments.json")


def public_bottle(item: dict, viewer_id: str | None = None, include_private: bool = False) -> dict:
    author = users.find(item["user_id"]) or {}
    response = {
        "id": item["id"],
        "content": item["content"],
        "nickname": author.get("nickname", "匿名旅人"),
        "avatar": author.get("avatar", "匿"),
        "region": item.get("region", "未标注"),
        "created_at": item["created_at"],
        "type": "bottle",
        "views": item.get("views", 0),
        "reply": item.get("reply") if viewer_id == item["user_id"] else None,
        "is_author": viewer_id == item["user_id"],
        "liked": any(
            like["item_id"] == item["id"] and like["user_id"] == viewer_id for like in likes.all()
        ),
    }
    if include_private or viewer_id == item["user_id"]:
        response["likes"] = sum(1 for like in likes.all() if like["item_id"] == item["id"])
        response["comments"] = [
            comment for comment in comments.all() if comment["item_id"] == item["id"]
        ]
    return response


@bottle_bp.post("")
def publish_bottle():
    payload = request.get_json(silent=True) or {}
    error = validate_content(payload.get("content"))
    if error:
        return jsonify({"error": {"message": error}}), 400
    user = users.find(str(payload.get("user_id", "")))
    if not user:
        return jsonify({"error": {"message": "请先创建匿名身份。"}}), 400
    review = moderate_locally(payload["content"].strip())
    if not review["safe"]:
        return jsonify({"error": {"message": review["reason"], "review": review}}), 422
    item = {
        "id": new_id("bottle", payload["content"]),
        "content": payload["content"].strip(),
        "user_id": user["id"],
        "region": user["region"],
        "created_at": utc_now(),
        "tags": extract_tags(payload["content"]),
        "views": 0,
        "reply": generate_reply(user["nickname"], payload["content"]),
    }
    bottles.append(item)
    return jsonify({"data": public_bottle(item, user["id"], True), "review": review}), 201


@bottle_bp.get("/discover")
def discover_bottle():
    viewer_id = request.args.get("user_id", "")
    mode = request.args.get("mode", "random")
    candidates = [item for item in bottles.all() if item["user_id"] != viewer_id]
    if not candidates:
        return jsonify({"data": None, "message": "海面暂时安静，稍后再来。"})
    if mode == "echo":
        own_content = " ".join(
            item["content"] for item in bottles.all() if item["user_id"] == viewer_id
        )
        own_tags = set(extract_tags(own_content))
        item = max(candidates, key=lambda candidate: recommendation_score(candidate, own_tags))
    else:
        import random

        item = random.choice(candidates)
    records = bottles.all()
    for record in records:
        if record["id"] == item["id"]:
            record["views"] = record.get("views", 0) + 1
            item = record
            break
    bottles.replace_all(records)
    return jsonify({"data": public_bottle(item, viewer_id)})


@bottle_bp.get("/<bottle_id>")
def get_bottle(bottle_id: str):
    item = bottles.find(bottle_id)
    if not item:
        return jsonify({"error": {"message": "这只漂流瓶已经飘远了。"}}), 404
    return jsonify({"data": public_bottle(item, request.args.get("user_id"))})


@bottle_bp.post("/<bottle_id>/likes")
def toggle_like(bottle_id: str):
    item = bottles.find(bottle_id)
    payload = request.get_json(silent=True) or {}
    user_id = str(payload.get("user_id", ""))
    if not item or not users.find(user_id):
        return jsonify({"error": {"message": "无效的漂流瓶或身份。"}}), 400
    records = likes.all()
    existing = next(
        (like for like in records if like["item_id"] == bottle_id and like["user_id"] == user_id), None
    )
    if existing:
        records.remove(existing)
        liked = False
    else:
        records.append({"id": new_id("like", bottle_id), "item_id": bottle_id, "user_id": user_id})
        liked = True
    likes.replace_all(records)
    return jsonify({"data": {"liked": liked}})


@bottle_bp.post("/<bottle_id>/comments")
def create_comment(bottle_id: str):
    item = bottles.find(bottle_id)
    payload = request.get_json(silent=True) or {}
    error = validate_content(payload.get("content"))
    if not item or error or not users.find(str(payload.get("user_id", ""))):
        return jsonify({"error": {"message": error or "无效的漂流瓶或身份。"}}), 400
    comment = {
        "id": new_id("comment", bottle_id),
        "item_id": bottle_id,
        "user_id": str(payload["user_id"]),
        "content": payload["content"].strip(),
        "created_at": utc_now(),
    }
    comments.append(comment)
    return jsonify({"data": {"sent": True}}), 201


@bottle_bp.get("/mine/<user_id>")
def my_bottles(user_id: str):
    own = [item for item in bottles.all() if item["user_id"] == user_id]
    return jsonify({"data": [public_bottle(item, user_id, True) for item in reversed(own)]})

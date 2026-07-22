from flask import Blueprint, jsonify, request

from app.storage import UserStorage

user_bp = Blueprint("users", __name__)
users = UserStorage()


@user_bp.post("")
def create_user():
    payload = request.get_json(silent=True) or {}
    required = ("id", "nickname", "birthday", "gender")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return jsonify({"error": {"message": f"缺少字段：{', '.join(missing)}"}}), 400
    nickname = str(payload["nickname"]).strip()
    if not 1 <= len(nickname) <= 20:
        return jsonify({"error": {"message": "昵称长度需在 1 到 20 个字符之间。"}}), 400
    user = {
        "id": str(payload["id"]),
        "nickname": nickname,
        "birthday": str(payload["birthday"]),
        "gender": str(payload["gender"]),
        "region": str(payload.get("region", "未标注")),
        "avatar": nickname[0],
    }
    return jsonify({"data": users.upsert(user)}), 201


@user_bp.get("/<user_id>")
def get_user(user_id: str):
    user = users.find(user_id)
    if not user:
        return jsonify({"error": {"message": "用户不存在。"}}), 404
    return jsonify({"data": user})

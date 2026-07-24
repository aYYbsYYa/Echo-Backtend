import base64
import binascii
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, send_file

from app.config import Config
from app.services.content_service import new_id, utc_now, validate_content
from app.storage import CapsuleStorage, UserStorage

capsule_bp = Blueprint("capsules", __name__)
capsules = CapsuleStorage()
users = UserStorage()

# 可选的等待时长（秒）。minute 供演示/体验完整流程使用。
DURATIONS: dict[str, tuple[int, str]] = {
    "minute": (60, "1 分钟"),
    "month1": (30 * 24 * 3600, "1 个月"),
    "month3": (91 * 24 * 3600, "3 个月"),
    "month6": (182 * 24 * 3600, "半年"),
    "month12": (365 * 24 * 3600, "一年"),
}

# 自定义时长的允许范围：最短 1 分钟，最长 10 年
CUSTOM_MIN_SECONDS = 60
CUSTOM_MAX_SECONDS = 10 * 365 * 24 * 3600


def humanize_seconds(seconds: int) -> str:
    if seconds < 3600:
        return f"{max(1, seconds // 60)} 分钟"
    if seconds < 86_400:
        return f"{seconds // 3600} 小时"
    days = seconds // 86_400
    if days < 30:
        return f"{days} 天"
    if days < 365:
        return f"{days // 30} 个月"
    return f"{days // 365} 年"


def duration_label(item: dict) -> str:
    duration = item.get("duration", "month1")
    if duration in DURATIONS:
        return DURATIONS[duration][1]
    # 自定义时长：按封存总时长折算
    total = max(0, int(item.get("custom_seconds", 0)))
    return humanize_seconds(total) if total else "一段时光"

# 可选情绪标签（写信时的当下心境）
MOODS = ("expect", "lost", "miss", "grateful", "resolve", "calm")

# 配图：随信一起被时间封存。base64 data URL，解码后不超过 1.5MB
IMAGE_DIR = Config.DATA_DIR / "capsule_images"
MAX_IMAGE_BYTES = 1536 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def save_capsule_image(capsule_id: str, data_url: str) -> str | None:
    """解析 data URL 并落盘，返回错误信息（None 表示成功）。"""
    try:
        header, encoded = data_url.split(",", 1)
        mime = header.removeprefix("data:").removesuffix(";base64")
        ext = ALLOWED_IMAGE_TYPES[mime]
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, KeyError, binascii.Error):
        return "配图格式不支持，仅接受 JPG / PNG / WebP。"
    if len(raw) > MAX_IMAGE_BYTES:
        return "配图太大了，请压缩到 1.5MB 以内。"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    (IMAGE_DIR / f"{capsule_id}{ext}").write_bytes(raw)
    return None


def find_capsule_image(capsule_id: str):
    for ext in ALLOWED_IMAGE_TYPES.values():
        path = IMAGE_DIR / f"{capsule_id}{ext}"
        if path.exists():
            return path
    return None


def parse_time(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def remaining_seconds(item: dict) -> int:
    unlock_at = parse_time(item["unlock_at"])
    delta = unlock_at - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds()))


def is_unlocked(item: dict) -> bool:
    return remaining_seconds(item) == 0


def waited_label(item: dict) -> str:
    """从埋藏到开启，时间沉淀了多久。"""
    created = parse_time(item["created_at"])
    end = parse_time(item["opened_at"]) if item.get("opened_at") else datetime.now(timezone.utc)
    seconds = max(0, int((end - created).total_seconds()))
    if seconds < 3600:
        return f"{max(1, seconds // 60)} 分钟"
    if seconds < 24 * 3600:
        return f"{seconds // 3600} 小时"
    days = seconds // 86400
    if days < 30:
        return f"{days} 天"
    if days < 365:
        return f"{days // 30} 个月"
    return f"{days // 365} 年"


def public_capsule(item: dict, viewer_id: str | None, reveal: bool = False) -> dict | None:
    """序列化胶囊。内容只在两种情况下下发：到期后显式开启（reveal），或曾经开启过。"""
    if viewer_id != item["user_id"]:
        return None
    unlocked = is_unlocked(item)
    duration_key = item.get("duration", "month1")
    opened = bool(item.get("opened_at"))
    response = {
        "id": item["id"],
        "type": "capsule",
        "mood": item.get("mood"),
        "duration": duration_key,
        "duration_label": duration_label(item),
        "created_at": item["created_at"],
        "unlock_at": item["unlock_at"],
        "opened_at": item.get("opened_at"),
        "is_unlocked": unlocked,
        "remaining_seconds": remaining_seconds(item),
        "waited_label": waited_label(item),
        "has_image": bool(item.get("has_image")),
        # 未沉淀好的信绝不泄露；已开启过的可直接随列表下发
        "content": item["content"] if (unlocked and reveal) or opened else None,
    }
    return response


@capsule_bp.post("")
def bury_capsule():
    payload = request.get_json(silent=True) or {}
    error = validate_content(payload.get("content"))
    if error:
        return jsonify({"error": {"message": error}}), 400
    user = users.find(str(payload.get("user_id", "")))
    if not user:
        return jsonify({"error": {"message": "请先创建匿名身份。"}}), 400

    duration = str(payload.get("duration", "month1"))
    custom_seconds: int | None = None
    if duration == "custom":
        try:
            custom_seconds = int(payload.get("custom_seconds", 0))
        except (TypeError, ValueError):
            custom_seconds = 0
        if not CUSTOM_MIN_SECONDS <= custom_seconds <= CUSTOM_MAX_SECONDS:
            return jsonify({"error": {"message": "自定义时长需在 1 分钟到 10 年之间。"}}), 400
        seconds = custom_seconds
    elif duration in DURATIONS:
        seconds, _ = DURATIONS[duration]
    else:
        return jsonify({"error": {"message": "无效的等待时长。"}}), 400

    mood = payload.get("mood")
    if mood is not None and mood not in MOODS:
        return jsonify({"error": {"message": "无效的心情标签。"}}), 400

    now = datetime.now(timezone.utc)
    content = payload["content"].strip()
    capsule_id = new_id("capsule", content)

    # 配图（可选）：与信一起封存
    has_image = False
    image_data_url = payload.get("image")
    if image_data_url:
        if not isinstance(image_data_url, str):
            return jsonify({"error": {"message": "配图数据无效。"}}), 400
        image_error = save_capsule_image(capsule_id, image_data_url)
        if image_error:
            return jsonify({"error": {"message": image_error}}), 400
        has_image = True

    item = {
        "id": capsule_id,
        "content": content,
        "user_id": user["id"],
        "mood": mood,
        "duration": duration,
        "custom_seconds": custom_seconds,
        "has_image": has_image,
        "created_at": now.isoformat(),
        "unlock_at": (now + timedelta(seconds=seconds)).isoformat(),
        "opened_at": None,
    }
    capsules.append(item)
    return jsonify({"data": public_capsule(item, user["id"])}), 201


@capsule_bp.get("/mine/<user_id>")
def my_capsules(user_id: str):
    """我的林地：按解锁时间升序，快到期的排在前面。内容一律不下发。"""
    own = [item for item in capsules.all() if item["user_id"] == user_id]
    own.sort(key=lambda item: item["unlock_at"])
    data = [public_capsule(item, user_id) for item in own]
    return jsonify(
        {
            "data": data,
            "meta": {
                "total": len(data),
                "unlockable": sum(1 for entry in data if entry["is_unlocked"] and not entry["opened_at"]),
            },
        }
    )


@capsule_bp.post("/<capsule_id>/open")
def open_capsule(capsule_id: str):
    """开启胶囊：到期才允许；首次开启记录 opened_at。"""
    payload = request.get_json(silent=True) or {}
    user_id = str(payload.get("user_id", ""))
    item = capsules.find(capsule_id)
    if not item or item["user_id"] != user_id:
        return jsonify({"error": {"message": "这棵树洞不属于你。"}}), 404
    if not is_unlocked(item):
        return (
            jsonify(
                {
                    "error": {
                        "message": "时间还没到，再等等。",
                        "remaining_seconds": remaining_seconds(item),
                    }
                }
            ),
            423,
        )
    if not item.get("opened_at"):
        records = capsules.all()
        for record in records:
            if record["id"] == capsule_id:
                record["opened_at"] = utc_now()
                item = record
                break
        capsules.replace_all(records)
    return jsonify({"data": public_capsule(item, user_id, reveal=True)})


@capsule_bp.get("/<capsule_id>/image")
def capsule_image(capsule_id: str):
    """胶囊配图：仅作者可见，且必须等时间沉淀好（未解锁前连图也看不到）。"""
    user_id = str(request.args.get("user_id", ""))
    item = capsules.find(capsule_id)
    if not item or item["user_id"] != user_id:
        return jsonify({"error": {"message": "这张图不属于你。"}}), 404
    if not is_unlocked(item):
        return jsonify({"error": {"message": "时间还没到，图也在沉睡。"}}), 423
    path = find_capsule_image(capsule_id)
    if not path:
        return jsonify({"error": {"message": "这封信没有配图。"}}), 404
    return send_file(path, max_age=3600)

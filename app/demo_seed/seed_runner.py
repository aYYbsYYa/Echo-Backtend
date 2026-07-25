from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import Config
from app.storage.json_repository import JsonRepository

from .seed_data import build_demo_data

ASSET_COPIES = {
    "晚上下雨逛街.jpeg": "demo_rainy_walk.jpeg",
    "晚霞.png": "demo_sunset.png",
}
# 胶囊配图：目标文件名必须与胶囊 ID 对应（<capsule_id>.<ext>）
CAPSULE_IMAGE_COPIES = {
    "向日葵.png": "demo_capsule_soon.png",
}
EXPECTED_COUNTS = {
    "users": 10,
    "bottles": 10,
    "planes": 10,
    "comments": 28,
    "likes": 76,
    "capsules": 4,
    "echo_conversations": 2,
    "echo_messages": 10,
    "echo_profiles": 1,
    "agent_profiles": 4,
    "agent_matches": 1,
    "agent_dialogues": 1,
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"演示数据校验失败：{message}")


def _unique_ids(records: list[dict[str, Any]], collection: str) -> set[str]:
    ids = [item.get("id") for item in records]
    _require(all(isinstance(item_id, str) and item_id for item_id in ids), f"{collection} 存在无效 ID")
    _require(len(ids) == len(set(ids)), f"{collection} 存在重复 ID")
    return set(ids)


def validate_demo_data(data: dict[str, list[dict[str, Any]]]) -> None:
    _require(set(data) == set(Config.JSON_FILES), "集合清单与 Config.JSON_FILES 不一致")
    for collection, expected in EXPECTED_COUNTS.items():
        _require(len(data[collection]) == expected, f"{collection} 数量应为 {expected}")
        _unique_ids(data[collection], collection)

    users = {item["id"]: item for item in data["users"]}
    content = {item["id"]: item for item in data["bottles"] + data["planes"]}
    for collection in ("bottles", "planes", "capsules"):
        _require(all(item.get("user_id") in users for item in data[collection]), f"{collection} 引用了不存在的用户")

    like_pairs = [(item.get("item_id"), item.get("user_id")) for item in data["likes"]]
    _require(len(like_pairs) == len(set(like_pairs)), "同一用户重复点赞同一内容")
    for item in data["likes"]:
        _require(item.get("item_id") in content and item.get("user_id") in users, "点赞关联无效")
        _require(content[item["item_id"]]["user_id"] != item["user_id"], "内容作者不能点赞自己的内容")
    for item in data["comments"]:
        _require(item.get("item_id") in content and item.get("user_id") in users, "留言关联无效")
        _require(item.get("nickname") == users[item["user_id"]]["nickname"], "留言昵称与用户不一致")

    for item in data["capsules"]:
        created_at = datetime.fromisoformat(item["created_at"])
        unlock_at = datetime.fromisoformat(item["unlock_at"])
        opened_at = datetime.fromisoformat(item["opened_at"]) if item.get("opened_at") else None
        _require(unlock_at >= created_at, "胶囊解锁时间早于创建时间")
        _require(opened_at is None or opened_at >= unlock_at, "胶囊在解锁前被开启")

    conversation_users = {item["id"]: item["user_id"] for item in data["echo_conversations"]}
    _require(all(user_id in users for user_id in conversation_users.values()), "灵笺会话用户无效")
    for message in data["echo_messages"]:
        _require(message.get("conversation_id") in conversation_users, "灵笺消息会话无效")
    for profile in data["echo_profiles"]:
        _require(profile.get("user_id") in users, "灵笺画像用户无效")
        related_users = {user_id for user_id in conversation_users.values() if user_id == profile["user_id"]}
        _require(bool(related_users), "灵笺画像没有对应会话")

    agent_ids = {item["id"] for item in data["agent_profiles"]}
    for match in data["agent_matches"]:
        _require(match.get("user_id") in agent_ids, "Agent 匹配源用户无效")
        _require(all(item.get("user_id") in agent_ids for item in match.get("matches", [])), "Agent 匹配目标用户无效")
    for dialogue in data["agent_dialogues"]:
        _require(dialogue.get("user_id") in agent_ids and dialogue.get("target_user_id") in agent_ids, "Agent 对话用户无效")
        _require(all(item.get("user_id") in agent_ids for item in dialogue.get("conversation", [])), "Agent 对话消息用户无效")


def _clear_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def reset_and_seed_demo_data(now: datetime | None = None) -> dict[str, int]:
    data = build_demo_data(now)
    validate_demo_data(data)
    asset_dir = Config.BASE_DIR / "docs" / "demo-data"
    asset_sources = {
        target_name: asset_dir / source_name
        for source_name, target_name in ASSET_COPIES.items()
    }
    capsule_image_sources = {
        target_name: asset_dir / source_name
        for source_name, target_name in CAPSULE_IMAGE_COPIES.items()
    }
    for source in list(asset_sources.values()) + list(capsule_image_sources.values()):
        if not source.is_file():
            raise RuntimeError(f"演示图片不存在：{source}")

    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in Config.JSON_FILES:
        JsonRepository(Config.DATA_DIR / f"{name}.json").replace_all(data[name])

    _clear_directory(Config.UPLOAD_DIR)
    capsule_image_dir = Config.DATA_DIR / "capsule_images"
    _clear_directory(capsule_image_dir)
    for target_name, source in asset_sources.items():
        shutil.copy2(source, Config.UPLOAD_DIR / target_name)
    for target_name, source in capsule_image_sources.items():
        shutil.copy2(source, capsule_image_dir / target_name)

    counts = {name: len(records) for name, records in data.items()}
    print(
        "[demo-seed] reset complete: "
        f"users={counts['users']} bottles={counts['bottles']} "
        f"planes={counts['planes']} capsules={counts['capsules']}"
    )
    return counts

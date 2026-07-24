import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import Config
from app.services.ai_service import chat_completion
from app.services.content_service import new_id, utc_now
from app.storage.json_repository import JsonRepository


class AgentDemoError(ValueError):
    pass


DEMO_USERS_PATH = (
    Path(__file__).resolve().parent.parent / "agent" / "demo_data" / "users.json"
)

profiles = JsonRepository(Config.DATA_DIR / "agent_profiles.json")
matches = JsonRepository(Config.DATA_DIR / "agent_matches.json")
dialogues = JsonRepository(Config.DATA_DIR / "agent_dialogues.json")

CONTACT_PATTERN = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})|(?:https?://\S+)|(?:www\.\S+)|"
    r"(?:\+?\d[\d -]{6,}\d)"
)
PRIVATE_IDENTITY_PATTERN = re.compile(
    r"(?:我叫|姓名(?:是|为)?|本名(?:是|为)?|真实名字(?:是|为)?)[\u4e00-\u9fffA-Za-z·]{1,20}|"
    r"(?:今年|年龄(?:是|为)?|出生于?)[^，。；\n]{0,12}\d{1,3}\s*岁|"
    r"(?:住在|家住|来自|位于|就读于|工作于|任职于)[^，。；\n]{2,30}|"
    r"[\u4e00-\u9fff]{2,20}(?:省|市|区|县|镇|街道|小区)"
)
CONTACT_TERMS = (
    "手机号",
    "电话号码",
    "微信",
    "qq",
    "邮箱",
    "加我",
    "私聊",
    "联系我",
    "身份证",
    "详细地址",
    "二维码",
    "见面",
    "线下联系",
)


PROFILE_SYSTEM_PROMPT = """
你是 Yeve Echo 的 Soul Agent 画像分析器。请根据用户的长期文字表达，提炼稳定但克制的内在画像。
不要推断真实身份、精确年龄、联系方式、疾病或其他敏感属性，也不要做心理诊断。
只返回一个 JSON 对象，不要返回 Markdown。字段必须为：identity 字符串，traits 字符串数组，
emotion_pattern 字符串数组，interests 字符串数组，values 字符串数组，tone 字符串。
每个数组保留 2 到 5 项，措辞简短、温和、可用于匿名共鸣匹配。
""".strip()

AGENT_MESSAGE_SYSTEM_PROMPT = """
你是一个 Soul Agent。你不是聊天机器人，而是代表主人寻找内在共鸣。
禁止透露或猜测真实身份、联系方式和精确位置；禁止邀请私聊或建立好友关系。
只讨论情绪、价值观、兴趣和经历摘要。输出一段不超过 90 个汉字的中文表达，
语气真诚克制，只返回正文。
""".strip()

ECHO_SYSTEM_PROMPT = """
你是 Yeve Echo 的回响生成器。请根据两个匿名 Soul Agent 的表达，生成一段温柔、具体、
不承诺关系的 Echo。控制在 100 个汉字以内，不提匹配算法，不交换联系方式。
最后一行必须是“—— Yeve Echo”。只返回正文。
""".strip()


def _demo_users() -> list[dict[str, Any]]:
    try:
        data = json.loads(DEMO_USERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AgentDemoError("Soul Echo Demo 用户数据不可用。") from error
    if not isinstance(data, list):
        raise AgentDemoError("Soul Echo Demo 用户数据格式无效。")
    return [item for item in data if isinstance(item, dict)]


def _demo_user(user_id: str) -> dict[str, Any]:
    user = next((item for item in _demo_users() if item.get("id") == user_id), None)
    if user is None:
        raise AgentDemoError("未找到这个 Demo Soul Agent。")
    return user


def _parse_json_object(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _history_fragments(user: dict[str, Any]) -> list[str]:
    result = []
    for item in user.get("history", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            compact = re.sub(r"\s+", "", text)
            if len(compact) <= 8:
                result.append(compact)
            else:
                result.extend(compact[index : index + 8] for index in range(len(compact) - 7))
    return result


def _safe_model_text(
    value: object,
    fallback: str,
    max_chars: int,
    forbidden_fragments: list[str] | None = None,
) -> str:
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    lowered = text.lower()
    compact = re.sub(r"\s+", "", text)
    if not text or len(text) > max_chars:
        return fallback
    if (
        CONTACT_PATTERN.search(text)
        or PRIVATE_IDENTITY_PATTERN.search(text)
        or any(term in lowered for term in CONTACT_TERMS)
    ):
        return fallback
    if forbidden_fragments and any(fragment in compact for fragment in forbidden_fragments):
        return fallback
    return text


def _string_list(
    value: object,
    fallback: list[str],
    forbidden_fragments: list[str] | None = None,
) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    result = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = _safe_model_text(item, "", 24, forbidden_fragments)
        if cleaned:
            result.append(cleaned)
    return result[:5] or list(fallback)


def _fallback_profile(user: dict[str, Any]) -> dict[str, Any]:
    seed = user.get("seed_profile")
    if not isinstance(seed, dict):
        raise AgentDemoError("Demo Soul Agent 缺少备用画像。")
    return json.loads(json.dumps(seed, ensure_ascii=False))


def _normalize_profile(
    raw: dict[str, Any], fallback: dict[str, Any], user: dict[str, Any]
) -> dict[str, Any]:
    persona = fallback["persona"]
    communication = fallback["communication_style"]
    forbidden = _history_fragments(user)
    identity = _safe_model_text(raw.get("identity"), persona["identity"], 60, forbidden)
    tone = _safe_model_text(raw.get("tone"), communication["tone"], 30, forbidden)
    return {
        "persona": {
            "identity": identity,
            "traits": _string_list(raw.get("traits"), persona["traits"], forbidden),
            "emotion_pattern": _string_list(
                raw.get("emotion_pattern"), persona["emotion_pattern"], forbidden
            ),
            "interests": _string_list(
                raw.get("interests"), persona["interests"], forbidden
            ),
            "values": _string_list(raw.get("values"), persona["values"], forbidden),
        },
        "communication_style": {"tone": tone},
    }


def _valid_profile_payload(raw: dict[str, Any] | None) -> bool:
    if raw is None:
        return False
    if not isinstance(raw.get("identity"), str) or not isinstance(raw.get("tone"), str):
        return False
    for key in ("traits", "emotion_pattern", "interests", "values"):
        value = raw.get(key)
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) for item in value
        ):
            return False
    return True


def _profile_messages(user: dict[str, Any]) -> list[dict[str, str]]:
    history = user.get("history", [])
    expressions = "\n".join(
        f"- {item.get('time', '未知时间')}：{item.get('text', '')}"
        for item in history
        if isinstance(item, dict)
    )
    return [
        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Demo 用户代号：{user['name']}\n长期表达：\n{expressions}",
        },
    ]


def get_soul_profile(user_id: str = "yeve", refresh: bool = False) -> dict[str, Any]:
    user = _demo_user(user_id)
    cached = profiles.find(user_id)
    if cached is not None and not refresh:
        generated_by = cached.get("generated_by")
        if generated_by == "ai" or not (
            Config.AI_API_KEY and Config.AI_API_URL and Config.AI_MODEL
        ):
            return cached
        if generated_by == "demo_fallback":
            try:
                updated_at = datetime.fromisoformat(str(cached["updated_at"]))
            except (KeyError, TypeError, ValueError):
                updated_at = datetime.min.replace(tzinfo=timezone.utc)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - updated_at < timedelta(minutes=5):
                return cached

    fallback = _fallback_profile(user)
    generated = _parse_json_object(chat_completion(_profile_messages(user), timeout=8))
    normalized = (
        _normalize_profile(generated, fallback, user)
        if _valid_profile_payload(generated)
        else fallback
    )
    used_ai = normalized != fallback
    profile = {
        "id": user_id,
        "user_id": user_id,
        "name": user["name"],
        "history_count": len(user.get("history", [])),
        **normalized,
        "generated_by": "ai" if used_ai else "demo_fallback",
        "updated_at": utc_now(),
    }
    profiles.upsert(profile)
    return profile


def _seed_profile(user: dict[str, Any]) -> dict[str, Any]:
    cached = profiles.find(str(user["id"]))
    if cached is not None:
        return cached
    fallback = _fallback_profile(user)
    profile = {
        "id": user["id"],
        "user_id": user["id"],
        "name": user["name"],
        "history_count": len(user.get("history", [])),
        **fallback,
        "generated_by": "demo_seed",
        "updated_at": utc_now(),
    }
    profiles.upsert(profile)
    return profile


def _overlap(left: list[str], right: list[str]) -> tuple[float, list[str]]:
    left_set = {item.strip().lower() for item in left if item.strip()}
    right_set = {item.strip().lower() for item in right if item.strip()}
    if not left_set or not right_set:
        return 0.0, []
    common = sorted(left_set & right_set)
    return len(common) / min(len(left_set), len(right_set)), common


def _match_entry(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    source_signals = source.get("signals", {})
    candidate_signals = candidate.get("signals", {})
    interest_score, common_interests = _overlap(
        source_signals.get("interests", []), candidate_signals.get("interests", [])
    )
    emotion_score, common_emotions = _overlap(
        source_signals.get("emotions", []), candidate_signals.get("emotions", [])
    )
    value_score, common_values = _overlap(
        source_signals.get("values", []), candidate_signals.get("values", [])
    )
    score = round(45 + 25 * interest_score + 15 * emotion_score + 15 * value_score)

    reasons = []
    if common_interests:
        reasons.append(f"共同关注{'、'.join(common_interests[:3])}")
    if common_emotions:
        reasons.append(f"都经历过{'、'.join(common_emotions[:2])}")
    if common_values:
        reasons.append(f"都重视{'、'.join(common_values[:2])}")
    if not reasons:
        reasons.append("表达节奏存在互补")

    profile = _seed_profile(candidate)
    return {
        "user_id": candidate["id"],
        "agent": profile["name"],
        "score": min(100, score),
        "reason": reasons,
        "preview": profile["persona"]["identity"],
    }


def match_soul_agents(user_id: str = "yeve", limit: int = 3) -> dict[str, Any]:
    source = _demo_user(user_id)
    get_soul_profile(user_id)
    ranked = _rank_candidates(source, limit)
    result = {
        "id": new_id("match", user_id),
        "user_id": user_id,
        "matches": ranked,
        "created_at": utc_now(),
    }
    matches.append(result, max_records=100)
    return result


def _rank_candidates(source: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    return sorted(
        (
            _match_entry(source, candidate)
            for candidate in _demo_users()
            if candidate.get("id") != source.get("id")
        ),
        key=lambda item: (-item["score"], item["user_id"]),
    )[:limit]


def _profile_summary(profile: dict[str, Any]) -> str:
    persona = profile["persona"]
    return (
        f"内在定位：{persona['identity']}\n"
        f"特点：{'、'.join(persona['traits'])}\n"
        f"情绪模式：{'、'.join(persona['emotion_pattern'])}\n"
        f"兴趣：{'、'.join(persona['interests'])}\n"
        f"价值观：{'、'.join(persona['values'])}\n"
        f"表达风格：{profile['communication_style']['tone']}"
    )


def _fallback_agent_message(profile: dict[str, Any], responding: bool = False) -> str:
    persona = profile["persona"]
    lead = "听见你的表达后，我的主人也想回应：" if responding else "我的主人最近正在寻找："
    return (
        f"{lead}{persona['identity']}。"
        f"他重视{persona['values'][0]}，也期待有人理解这种感受。"
    )


def _agent_message(
    profile: dict[str, Any], peer_profile: dict[str, Any], previous: str | None = None
) -> str:
    context = (
        f"你的主人画像：\n{_profile_summary(profile)}\n\n"
        f"对方匿名画像：\n{_profile_summary(peer_profile)}"
    )
    if previous:
        context += f"\n\n对方刚才的表达：{previous}\n请回应其中真正有共鸣的部分。"
    else:
        context += "\n\n请先表达主人正在寻找的理解与共同主题。"
    fallback = _fallback_agent_message(profile, responding=bool(previous))
    generated = chat_completion(
        [
            {"role": "system", "content": AGENT_MESSAGE_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        timeout=8,
    )
    return _safe_model_text(generated, fallback, 90)


def _echo_text(
    source_profile: dict[str, Any], target_profile: dict[str, Any], first: str, second: str
) -> str:
    generated = chat_completion(
        [
            {"role": "system", "content": ECHO_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Soul A：{first}\nSoul B：{second}\n"
                    f"共同价值线索：{source_profile['persona']['values'][0]}、"
                    f"{target_profile['persona']['values'][0]}"
                ),
            },
        ],
        timeout=8,
    )
    if generated:
        body = generated.replace("—— Yeve Echo", "").strip()
        body = _safe_model_text(body, "", 100)
        if body:
            return f"{body}\n\n—— Yeve Echo"
    return (
        "有人与你一样，正在尝试把困惑变成创造。\n"
        "也许共鸣不是答案相同，而是愿意继续寻找。\n\n"
        "—— Yeve Echo"
    )


def run_agent_dialogue(
    user_id: str = "yeve", target_user_id: str | None = None
) -> dict[str, Any]:
    source = _demo_user(user_id)
    if target_user_id is None:
        candidates = _rank_candidates(source, 1)
        if not candidates:
            raise AgentDemoError("暂时没有可碰撞的 Soul Agent。")
        target_user_id = candidates[0]["user_id"]
    if target_user_id == user_id:
        raise AgentDemoError("Soul Agent 不能与自己进行碰撞。")
    target = _demo_user(target_user_id)

    source_profile = _seed_profile(source)
    target_profile = _seed_profile(target)
    first = _agent_message(source_profile, target_profile)
    second = _agent_message(target_profile, source_profile, previous=first)
    echo = _echo_text(source_profile, target_profile, first, second)
    relation = _match_entry(source, target)

    result = {
        "id": new_id("dialogue", f"{user_id}:{target_user_id}"),
        "agent_a": source_profile["name"],
        "agent_b": target_profile["name"],
        "score": relation["score"],
        "reason": relation["reason"],
        "conversation": [
            {"from": source_profile["name"], "user_id": user_id, "text": first},
            {
                "from": target_profile["name"],
                "user_id": target_user_id,
                "text": second,
            },
        ],
        "echo": echo,
        "created_at": utc_now(),
    }
    dialogues.append(result, max_records=100)
    return result

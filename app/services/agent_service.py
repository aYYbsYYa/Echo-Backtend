import json
import re
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
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
MESSAGE_SIMILARITY_THRESHOLD = 0.86


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


def _distinctive_profile_item(
    profile: dict[str, Any],
    peer_profile: dict[str, Any],
    field: str,
    offset: int = 0,
) -> str:
    persona = profile["persona"]
    peer_persona = peer_profile["persona"]
    own_items = [
        item.strip()
        for item in persona.get(field, [])
        if isinstance(item, str) and item.strip()
    ]
    peer_items = {
        item.strip().lower()
        for item in peer_persona.get(field, [])
        if isinstance(item, str) and item.strip()
    }
    candidates = [item for item in own_items if item.strip().lower() not in peer_items]
    pool = candidates or own_items
    if not pool:
        return "真实感受"
    identity = str(profile.get("user_id") or profile.get("id") or profile.get("name", ""))
    stable_index = (sum(ord(character) for character in identity) + offset) % len(pool)
    return pool[stable_index]


def _normalized_message(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).lower()


def _repeats_conversation(text: str, conversation: list[dict[str, Any]]) -> bool:
    candidate = _normalized_message(text)
    if not candidate:
        return True
    for item in conversation:
        previous = _normalized_message(str(item.get("text", "")))
        if not previous:
            continue
        if candidate == previous:
            return True
        if SequenceMatcher(None, candidate, previous).ratio() >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False


def _fallback_agent_message(
    profile: dict[str, Any],
    peer_profile: dict[str, Any],
    round_number: int = 1,
    speaker_position: int = 0,
    variant: int = 0,
) -> str:
    persona = profile["persona"]
    interest = _distinctive_profile_item(
        profile, peer_profile, "interests", offset=round_number + speaker_position
    )
    value = _distinctive_profile_item(
        profile, peer_profile, "values", offset=round_number + speaker_position
    )
    if variant == 1:
        return f"{profile['name']}想从{interest}出发，和你一起确认{value}怎样进入真实生活。"
    if variant == 2:
        return f"对我的主人而言，此刻更重要的是{value}；{interest}只是抵达它的一条路径。"
    if variant == 3:
        return f"这次交流让我的主人重新看见{interest}，也更愿意把{value}落实为行动。"
    if variant == 4:
        return f"我的主人没有现成答案，但愿意围绕{value}，继续和你讨论{interest}。"
    if variant == 5:
        return f"如果只留下两个关键词，我的主人会选择{interest}与{value}，并从这里继续。"
    if variant == 6:
        return f"{value}是{profile['name']}此刻想守住的核心，而{interest}会是下一步实践。"
    if round_number == 1:
        if speaker_position == 0:
            return f"我的主人最近正在寻找：{persona['identity']}。他尤其在意{value}。"
        return f"听见你的开场后，我的主人也想回应：{persona['identity']}。他想从{interest}谈起。"
    if round_number == 2:
        if speaker_position == 0:
            return f"把上一轮的回应接回来，我的主人更想追问：{interest}怎样才能守住{value}，而不只停留在想法里？"
        return f"你把问题推进了一步。对我的主人来说，{interest}只有朝向{value}，才可能成为真实的改变。"
    if speaker_position == 0:
        return f"如果为这次相遇留下一个方向，我的主人愿意继续用{interest}靠近{value}。"
    return f"作为最后的回应，我的主人想补上一句：愿我们带着{value}，把{interest}继续做下去。"


def _unique_fallback_agent_message(
    profile: dict[str, Any],
    peer_profile: dict[str, Any],
    conversation: list[dict[str, Any]],
    round_number: int,
    speaker_position: int,
) -> str:
    for variant in range(7):
        fallback = _fallback_agent_message(
            profile,
            peer_profile,
            round_number=round_number,
            speaker_position=speaker_position,
            variant=variant,
        )
        if not _repeats_conversation(fallback, conversation):
            return fallback
    raise AgentDemoError("Soul Agent 无法生成不重复的安全表达。")


def _agent_message(
    profile: dict[str, Any],
    peer_profile: dict[str, Any],
    conversation: list[dict[str, Any]] | None = None,
    round_number: int = 1,
    speaker_position: int = 0,
) -> str:
    history = conversation or []
    context = (
        f"你的主人画像：\n{_profile_summary(profile)}\n\n"
        f"对方匿名画像：\n{_profile_summary(peer_profile)}"
    )
    if history:
        transcript = "\n".join(
            f"第{item['round']}轮 {item['from']}：{item['text']}" for item in history
        )
        context += f"\n\n此前对话：\n{transcript}"
    if round_number == 1 and not history:
        instruction = "请先表达主人正在寻找的理解与共同主题。"
    elif round_number == 1:
        instruction = "请回应对方第一轮表达中真正有共鸣的部分。"
    elif round_number == 2:
        instruction = "请在第二轮回应对方最新表达并推进共同主题，增加一个更具体的感受或思考。"
    else:
        instruction = "这是第三轮，请回应对方最新表达并从你主人的角度收束，留下克制而开放的一句话。"
    distinctive_interest = _distinctive_profile_item(
        profile, peer_profile, "interests", offset=round_number + speaker_position
    )
    distinctive_value = _distinctive_profile_item(
        profile, peer_profile, "values", offset=round_number + speaker_position
    )
    context += (
        f"\n\n当前是第 {round_number} 轮，你是本轮"
        f"{'先发言方' if speaker_position == 0 else '后发言方'}。{instruction}"
        f"请优先从你主人更独特的线索“{distinctive_interest}”或“{distinctive_value}”出发，"
        "不要复用此前任何消息的完整句子、开头句式或结论。"
    )
    fallback = _unique_fallback_agent_message(
        profile,
        peer_profile,
        history,
        round_number=round_number,
        speaker_position=speaker_position,
    )
    generated = chat_completion(
        [
            {"role": "system", "content": AGENT_MESSAGE_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        timeout=8,
    )
    candidate = _safe_model_text(generated, fallback, 90)
    return fallback if _repeats_conversation(candidate, history) else candidate


def _echo_text(
    source_profile: dict[str, Any],
    target_profile: dict[str, Any],
    conversation: list[dict[str, Any]],
) -> str:
    transcript = "\n".join(
        f"第{item['round']}轮 {item['from']}：{item['text']}" for item in conversation
    )
    generated = chat_completion(
        [
            {"role": "system", "content": ECHO_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"完整对话：\n{transcript}\n"
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


def _dialogue_session(
    user_id: str, target_user_id: str | None
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
    relation = _match_entry(source, target)
    return {
        "user_id": user_id,
        "target_user_id": target_user_id,
        "source_profile": source_profile,
        "target_profile": target_profile,
        "relation": relation,
    }


def _dialogue_messages(session: dict[str, Any]) -> Iterator[dict[str, Any]]:
    conversation: list[dict[str, Any]] = []
    speakers = (
        (
            session["source_profile"],
            session["target_profile"],
            session["user_id"],
        ),
        (
            session["target_profile"],
            session["source_profile"],
            session["target_user_id"],
        ),
    )
    for round_number in range(1, 4):
        for speaker_position, (profile, peer_profile, speaker_id) in enumerate(speakers):
            text = _agent_message(
                profile,
                peer_profile,
                conversation=conversation,
                round_number=round_number,
                speaker_position=speaker_position,
            )
            message = {
                "round": round_number,
                "from": profile["name"],
                "user_id": speaker_id,
                "text": text,
            }
            conversation.append(message)
            yield message


def _complete_dialogue(
    session: dict[str, Any], conversation: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(conversation) != 6:
        raise AgentDemoError("Soul Agent 对话未完整结束。")
    source_profile = session["source_profile"]
    target_profile = session["target_profile"]
    relation = session["relation"]
    echo = _echo_text(source_profile, target_profile, conversation)

    result = {
        "id": new_id(
            "dialogue", f"{session['user_id']}:{session['target_user_id']}"
        ),
        "user_id": session["user_id"],
        "target_user_id": session["target_user_id"],
        "agent_a": source_profile["name"],
        "agent_b": target_profile["name"],
        "score": relation["score"],
        "reason": relation["reason"],
        "conversation": conversation,
        "echo": echo,
        "created_at": utc_now(),
    }
    dialogues.append(result, max_records=100)
    return result


def run_agent_dialogue(
    user_id: str = "yeve", target_user_id: str | None = None
) -> dict[str, Any]:
    session = _dialogue_session(user_id, target_user_id)
    conversation = list(_dialogue_messages(session))
    return _complete_dialogue(session, conversation)


def stream_agent_dialogue(
    user_id: str = "yeve", target_user_id: str | None = None
) -> Iterator[dict[str, Any]]:
    session = _dialogue_session(user_id, target_user_id)

    def generate() -> Iterator[dict[str, Any]]:
        yield {
            "type": "start",
            "data": {
                "agent_a": session["source_profile"]["name"],
                "agent_b": session["target_profile"]["name"],
                "score": session["relation"]["score"],
                "reason": session["relation"]["reason"],
            },
        }
        conversation = []
        for message in _dialogue_messages(session):
            conversation.append(message)
            yield {"type": "message", "data": message}
        result = _complete_dialogue(session, conversation)
        yield {"type": "echo", "data": {"echo": result["echo"]}}
        yield {
            "type": "done",
            "data": {
                "dialogue_id": result["id"],
                "created_at": result["created_at"],
            },
        }

    return generate()


def _dialogue_belongs_to(record: dict[str, Any], user_id: str) -> bool:
    direct_ids = {record.get("user_id"), record.get("target_user_id")}
    if "user_id" in record or "target_user_id" in record:
        return user_id in direct_ids
    conversation = record.get("conversation")
    if not isinstance(conversation, list):
        conversation = []
    conversation_ids = {
        item.get("user_id")
        for item in conversation
        if isinstance(item, dict)
    }
    return user_id in direct_ids or user_id in conversation_ids


def list_agent_dialogues(user_id: str = "yeve", limit: int = 20) -> list[dict[str, Any]]:
    _demo_user(user_id)
    related = [
        record
        for record in dialogues.all()
        if isinstance(record, dict) and _dialogue_belongs_to(record, user_id)
    ]
    related.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return related[: max(0, limit)]


def delete_agent_dialogue(user_id: str, dialogue_id: str) -> dict[str, Any]:
    _demo_user(user_id)
    deleted = dialogues.delete(
        dialogue_id,
        predicate=lambda record: _dialogue_belongs_to(record, user_id),
    )
    if deleted is None:
        raise AgentDemoError("未找到可删除的历史回响。")
    return {"id": dialogue_id, "deleted": True}

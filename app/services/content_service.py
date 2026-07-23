import hashlib
import random
from datetime import datetime, timezone


TAG_RULES = {
    "学习": ("高考", "考试", "学习", "论文", "作业"),
    "成长": ("未来", "成长", "选择", "毕业", "努力"),
    "科技": ("ai", "编程", "代码", "科技", "互联网"),
    "青春": ("青春", "朋友", "学校", "夏天", "暗恋"),
    "孤独": ("孤独", "失眠", "难过", "想念", "一个人"),
    "自然": ("海", "风", "夜", "雨", "森林"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str, source: str) -> str:
    entropy = f"{source}:{utc_now()}:{random.random()}"
    return f"{prefix}_{hashlib.sha256(entropy.encode()).hexdigest()[:16]}"


def validate_content(content: object) -> str | None:
    if not isinstance(content, str):
        return "内容必须为文字。"
    text = content.strip()
    if not 1 <= len(text) <= 500:
        return "内容长度需在 1 到 500 个字符之间。"
    return None


def extract_tags(content: str) -> list[str]:
    lowered = content.lower()
    tags = [tag for tag, terms in TAG_RULES.items() if any(term in lowered for term in terms)]
    return tags or ["日常"]


def recommendation_score(candidate: dict, own_tags: set[str]) -> float:
    candidate_tags = set(candidate.get("tags", []))
    overlap = len(candidate_tags & own_tags)
    freshness = 1 / (1 + candidate.get("views", 0) * 0.03)
    return overlap * 3 + freshness + random.random() * 2

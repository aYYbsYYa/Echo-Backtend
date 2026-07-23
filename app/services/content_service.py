import hashlib
import random
from datetime import datetime, timezone


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

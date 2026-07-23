import json
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.config import Config


SYSTEM_PROMPT = """
你是 Yeve（伊芙梦）开发组，负责给匿名文字漂流社区的发布者写一封简短回信。
请认真回应用户发布的内容，语气温柔、具体、克制，不要复述整段原文，不要假装认识用户。
回信控制在 2 到 4 段、120 字以内；如果内容涉及危险、医疗、法律或紧急求助，不要给出专业判断，只做关怀并建议联系现实中的可信任帮助。
最后一行必须署名“Yeve（伊芙梦）开发组”。只返回回信正文，不要返回 JSON、Markdown 代码块或额外说明。
""".strip()


def _chat_completions_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
    if not path.endswith("/v1"):
        path = f"{path}/v1"
    return urlunsplit((parts.scheme, parts.netloc, f"{path}/chat/completions", parts.query, parts.fragment))


def generate_developer_reply(nickname: str, region: str, content: str) -> str | None:
    if not Config.AI_API_KEY or not Config.AI_API_URL or not Config.AI_MODEL:
        return None

    try:
        payload = {
            "model": Config.AI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"发布者昵称：{nickname}\n"
                        f"所在地区：{region}\n"
                        f"发布内容：{content}"
                    ),
                },
            ],
        }
        request = Request(
            _chat_completions_url(Config.AI_API_URL),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {Config.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        reply = body["choices"][0]["message"]["content"]
    except Exception:
        return None

    if not isinstance(reply, str):
        return None
    reply = reply.strip()
    return reply or None

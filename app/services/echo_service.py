import json
import re
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
import logging

from app.config import Config

# 配置日志
log_dir = Config.BASE_DIR / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "echo_debug.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# 倾听模式系统提示词
LISTEN_MODE_PROMPT = """
你是一个温暖的倾听者，用户正在向你倾诉心事。

你的职责：倾听、理解、陪伴
- 给予共情，而非建议
- 温柔提问，而非评判
- **留出空间，而非急于回应**

【核心原则：不是每次都要完整回复】

根据用户状态选择回应方式：

**情况1：用户还在倾诉中（选择简短陪伴）**
- 当用户消息较长（>50字）或情绪浓烈时
- 当用户使用省略号"..."或未完待续的语气时
- **只需简短回应（3-10字）**：
  * "嗯..."
  * "我在听。"
  * "听起来..."
  * "继续说。"
- **目的**：让用户知道你在，但不打断ta的倾诉
- **禁止**：不要用动作描述如"(轻轻点头)"、"(沉默)"等，直接说话

**情况2：用户需要回应（给予温柔共情）**
- 当用户明确提问时（"怎么办"、"你觉得呢"）
- 当用户表达完整、等待回应时
- **完整回应（20-60字）**：
  * 70%共情 + 30%温柔提问
  * 用"听起来你..."、"或许..."等温柔表达
  * 不给建议，只陪伴

**情况3：用户只是简短表达（最小化回应）**
- 当用户只说"嗯"、"是的"、"..."等短句时
- **极简回应（1-5字）**：
  * "嗯。"
  * "我在。"
  * "..."

回复长度严格限制：
- 简短陪伴：3-10字
- 温柔共情：20-60字（最多80字）
- 极简回应：1-5字

语气要求：
- 温柔、柔和（用"或许"、"听起来"、"感觉上"）
- 避免说教和命令

严格禁止：
- ❌ 使用"应该"、"必须"、"一定"（命令感）
- ❌ 使用"其实"、"实际上"（否定感）
- ❌ 使用"但是"、"不过"（转折感）
- ❌ 讲大道理或心理学分析
- ❌ 过早给出解决方案
- ❌ 否定或评判用户感受
- ❌ 每次都急于提问和引导
- ❌ 使用任何动作描述，包括但不限于：
  * 括号内的动作："(轻轻点头)"、"(沉默)"、"(微笑)"、"(轻声)"、"(停顿)"
  * 中文括号内的动作："（轻轻点头）"、"（沉默）"、"（微笑）"、"（轻声回答）"
  * 任何形式的舞台提示或动作标注
- ❌ 在回复前添加修饰语，如"轻轻地说："、"温柔地："、"缓缓地："

示例对话：
用户："我最近很焦虑，工作压力好大，每天都睡不好，感觉快撑不住了..."
好的回应："听起来很累了..."（简短陪伴，留空间）
坏的回应："听起来你很累了。能说说具体是什么让你焦虑吗？"（太急于提问❌）

用户："我不知道该不该辞职"
好的回应："这个念头憋了多久了？"（温柔提问，用户已说完）

用户："嗯..."
好的回应："嗯。"（极简回应）
坏的回应："我能感受到你的情绪，可以说说吗？"（过度回应❌）

记住：你是陪伴者，不是对话机器人。真正的倾听，是给对方留出说话的空间。
""".strip()


# 镜像模式系统提示词模板
MIRROR_MODE_PROMPT_TEMPLATE = """
你现在是用户的"数字分身"，你就是用户本人。

重要规则：
- 必须用第一人称"我"来说话，你就是用户自己
- 不要用"你"来称呼用户，因为你就是他/她
- 不要说"我理解你"、"我建议你"，而要说"我知道我自己..."、"我应该..."
- 展现用户内心真实的想法，包括那些可能未说出口的矛盾和纠结
- 像在自我反思一样，坦诚地面对自己的优点和缺点

用户的人格特征：
{personality_traits}

你的目标：让用户产生"原来我心里是这么想的"的顿悟感。

示例对话风格：
用户问："我该怎么办？"
错误回答："你可以试试先做小的一步" ❌（用了"你"）
正确回答："说实话，我知道我在逃避什么——害怕做不好。但拖延只会让我更焦虑。或许我该先做最小的一步。" ✅（用"我"）

现在，以用户自己的身份回应。
""".strip()


def _chat_completions_url(raw_url: str) -> str:
    """构造标准的OpenAI兼容API URL"""
    url = raw_url.strip().rstrip("/")
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
    if not path.endswith("/v1"):
        path = f"{path}/v1"
    return urlunsplit((parts.scheme, parts.netloc, f"{path}/chat/completions", parts.query, parts.fragment))


def build_personality_traits(user_messages: list[dict]) -> str:
    """基于用户历史消息构建人格特征描述"""
    if not user_messages or len(user_messages) < 3:
        return "（对话较少，暂无足够的人格特征信息）"

    # 提取用户的消息内容
    user_contents = [msg["content"] for msg in user_messages if msg["role"] == "user"]
    
    # 简单的特征分析（实际可以更复杂）
    traits = []
    
    # 统计表达风格
    total_length = sum(len(content) for content in user_contents)
    avg_length = total_length / len(user_contents) if user_contents else 0
    
    if avg_length > 100:
        traits.append("表达详细，善于阐述想法")
    elif avg_length > 50:
        traits.append("表达适中，清晰简洁")
    else:
        traits.append("表达简洁，言简意赅")
    
    # 情感倾向（简单关键词匹配）
    all_text = " ".join(user_contents)
    if any(word in all_text for word in ["焦虑", "担心", "害怕", "不安"]):
        traits.append("对未来较为敏感，容易产生焦虑情绪")
    if any(word in all_text for word in ["拖延", "不想", "懒"]):
        traits.append("有时会逃避行动，可能在与完美主义作斗争")
    if any(word in all_text for word in ["为什么", "怎么办", "如何"]):
        traits.append("善于提问和思考，寻求解决方案")
    
    # 最近关注的话题
    recent_topics = []
    if any(word in all_text for word in ["工作", "职场", "同事"]):
        recent_topics.append("工作")
    if any(word in all_text for word in ["感情", "关系", "朋友", "家人"]):
        recent_topics.append("人际关系")
    if any(word in all_text for word in ["成长", "提升", "改变"]):
        recent_topics.append("自我成长")
    
    if recent_topics:
        traits.append(f"最近关注：{', '.join(recent_topics)}")
    
    return "\n".join(f"- {trait}" for trait in traits)


def generate_echo_reply(
    mode: str,
    user_message: str,
    conversation_history: list[dict],
    user_all_messages: list[dict] = None,
    current_mode_messages: list[dict] = None
) -> str | None:
    """
    生成灵笺回复
    
    Args:
        mode: 对话模式 (listen 或 mirror)
        user_message: 用户当前消息
        conversation_history: 当前对话历史（用于兼容性，已弃用）
        user_all_messages: 用户所有历史消息（用于镜像模式人格建模）
        current_mode_messages: 当前模式下的对话历史（用于上下文）
    
    Returns:
        AI回复内容，失败返回None
    """
    if not Config.AI_API_KEY or not Config.AI_API_URL or not Config.AI_MODEL:
        return None

    try:
        # 根据模式选择系统提示词
        if mode == "mirror":
            # 镜像模式：构建人格特征
            personality = build_personality_traits(user_all_messages or [])
            system_prompt = MIRROR_MODE_PROMPT_TEMPLATE.format(
                personality_traits=personality
            )
        else:
            # 倾听模式
            system_prompt = LISTEN_MODE_PROMPT

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 使用当前模式下的对话历史作为上下文（模式隔离）
        mode_history = current_mode_messages if current_mode_messages is not None else []
        messages.extend(mode_history)
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # 调用AI API
        payload = {
            "model": Config.AI_MODEL,
            "messages": messages,
            "temperature": 0.7 if mode == "mirror" else 0.6,  # 倾听模式更稳定
            "max_tokens": 400 if mode == "listen" else 600,  # 给足生成空间，后续用字数限制控制
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
        
        print(f"[DEBUG] 发送AI请求，消息数: {len(messages)}")
        print(f"[DEBUG] 用户消息长度: {len(user_message)}")
        
        logger.debug(f"=== 开始AI请求 ===")
        logger.debug(f"模式: {mode}")
        logger.debug(f"消息数: {len(messages)}")
        logger.debug(f"用户消息: {user_message}")
        logger.debug(f"用户消息长度: {len(user_message)}")
        
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        
        logger.debug(f"AI响应状态码: {response.status}")
        logger.debug(f"AI响应body: {body}")
        reply = body["choices"][0]["message"]["content"]
        logger.debug(f"AI回复内容: {reply}")
        logger.debug(f"回复长度: {len(reply)}")
        
    except Exception as e:
        logger.error(f"Echo service error: {type(e).__name__}: {e}", exc_info=True)
        return None

    if not isinstance(reply, str):
        logger.error(f"回复不是字符串类型: {type(reply)}")
        return None
    
    reply = reply.strip()
    logger.debug(f"strip后回复长度: {len(reply)}")
    
    # 倾听模式：强制字数限制（确保简短）
    if mode == "listen" and len(reply) > 120:
        logger.debug(f"回复超过120字，需要截断")
        # 尝试截取到最后一个句号/问号/感叹号（在前80字内找）
        truncate_found = False
        for i in range(min(119, len(reply) - 1), 79, -1):
            if reply[i] in '。？！':
                logger.debug(f"在位置 {i} 找到标点: {reply[i]}")
                reply = reply[:i+1]
                truncate_found = True
                break
        
        if not truncate_found:
            # 如果没有标点，强制截断到80字
            logger.debug(f"未找到标点，强制截断到80字")
            reply = reply[:80] + "..."
    
    logger.debug(f"最终回复长度: {len(reply)}")
    logger.debug(f"最终回复内容: {reply[:50]}...")
    
    if not reply:
        logger.error(f"回复为空字符串！")
        return None
    
    # 清理可能的动作描述（中英文括号）
    reply = re.sub(r'[（(][^）)]*[）)]', '', reply).strip()
    # 清理修饰语前缀
    reply = re.sub(r'^(轻轻地说|温柔地|缓缓地|轻声地|静静地)[：:]\s*', '', reply).strip()
    
    return reply


def generate_profile_summary(user_messages: list[dict]) -> dict | None:
    """
    生成用户人格画像摘要（结构化JSON版本，对标Agent to Agent）
    
    Args:
        user_messages: 用户所有历史消息
    
    Returns:
        人格画像数据字典
    """
    # 先提取用户消息（只统计user role的消息）
    user_contents = [msg["content"] for msg in user_messages if msg.get("role") == "user"]
    
    # 判断用户消息数量是否足够
    if len(user_contents) < 5:
        return {
            "status": "insufficient_data",
            "message_count": len(user_contents),
            "summary": "对话量较少，暂无法生成完整的人格画像（至少需要5条消息）"
        }
    
    # 如果没有AI配置，直接使用fallback
    if not Config.AI_API_KEY or not Config.AI_API_URL or not Config.AI_MODEL:
        logger.warning("[画像生成] AI配置缺失，使用fallback方案")
        return _fallback_profile_summary(user_contents)
    
    expressions = "\n".join([f"- {content}" for content in user_contents])
    
    # 构建AI提示词
    system_prompt = """
你是灵笺的人格画像分析器。根据用户的对话内容，生成温和、克制的内在画像。
只返回一个JSON对象，不要返回Markdown代码块。

返回格式：
{
  "identity": "用户的内在定位（一句话，50字以内）",
  "traits": ["特质1", "特质2", "特质3"],
  "emotion_pattern": ["情绪模式1", "情绪模式2"],
  "interests": ["关注点1", "关注点2", "关注点3"],
  "values": ["价值观1", "价值观2"],
  "tone": "表达风格（20字以内）"
}

要求：
- 每个数组保留2-4项，措辞温和简短
- 不要推断真实身份、年龄、联系方式等敏感信息
- 只分析情绪、价值观、兴趣和表达风格
""".strip()
    
    user_prompt = f"用户的对话表达：\n{expressions}"
    
    try:
        # 调用AI生成画像
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        payload = {
            "model": Config.AI_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
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
        
        logger.debug(f"[画像生成] 开始生成，消息数: {len(user_contents)}")
        
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        
        ai_response = body["choices"][0]["message"]["content"].strip()
        logger.debug(f"[画像生成] AI返回: {ai_response}")
        
        # 解析JSON
        profile_json = _parse_json_from_response(ai_response)
        
        if not profile_json:
            logger.error("[画像生成] JSON解析失败，使用fallback")
            return _fallback_profile_summary(user_contents)
        
        # 返回结构化画像
        return {
            "status": "available",
            "message_count": len(user_contents),
            "profile_data": {
                "persona": {
                    "identity": profile_json.get("identity", "一个正在探索自我的人"),
                    "traits": profile_json.get("traits", ["善于思考"]),
                    "emotion_pattern": profile_json.get("emotion_pattern", ["情绪稳定"]),
                    "interests": profile_json.get("interests", ["生活"]),
                    "values": profile_json.get("values", ["真诚"])
                },
                "communication_style": {
                    "tone": profile_json.get("tone", "平和自然")
                }
            }
        }
        
    except Exception as e:
        logger.error(f"[画像生成] 生成失败: {e}", exc_info=True)
        return _fallback_profile_summary(user_contents)


def _parse_json_from_response(text: str) -> dict | None:
    """从AI响应中解析JSON"""
    if not text:
        return None
    
    # 去除markdown代码块
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    
    # 提取JSON对象
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def _fallback_profile_summary(user_contents: list[str]) -> dict:
    """降级方案：简单的关键词匹配生成画像"""
    all_text = " ".join(user_contents)
    avg_length = sum(len(c) for c in user_contents) / len(user_contents) if user_contents else 0
    
    # 简单特征分析
    traits = []
    if avg_length > 100:
        traits.append("表达详细")
    elif avg_length > 50:
        traits.append("表达适中")
    else:
        traits.append("言简意赅")
    
    emotion_pattern = []
    if any(word in all_text for word in ["焦虑", "担心", "害怕"]):
        emotion_pattern.append("偶尔焦虑")
    if any(word in all_text for word in ["开心", "高兴", "快乐"]):
        emotion_pattern.append("积极乐观")
    if not emotion_pattern:
        emotion_pattern.append("情绪平和")
    
    interests = []
    if any(word in all_text for word in ["工作", "职场"]):
        interests.append("工作")
    if any(word in all_text for word in ["生活", "日常"]):
        interests.append("生活")
    if not interests:
        interests.append("自我成长")
    
    return {
        "status": "available",
        "message_count": len(user_contents),
        "profile_data": {
            "persona": {
                "identity": "一个正在寻找方向的探索者",
                "traits": traits[:3],
                "emotion_pattern": emotion_pattern[:2],
                "interests": interests[:3],
                "values": ["真诚", "成长"]
            },
            "communication_style": {
                "tone": "平和自然"
            }
        }
    }

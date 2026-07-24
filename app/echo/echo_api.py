import sys
from flask import Blueprint, jsonify, request

from app.config import Config
from app.services.echo_service import generate_echo_reply, generate_profile_summary
from app.storage.echo_storage import EchoStorage

echo_bp = Blueprint("echo", __name__)
storage = EchoStorage(Config.DATA_DIR)

def log(msg):
    """强制输出日志到stderr"""
    print(msg, file=sys.stderr, flush=True)


@echo_bp.post("/conversations")
def create_conversation():
    """创建新的灵笺对话会话"""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    mode = data.get("mode", "listen")  # 默认倾听模式

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    if mode not in ["listen", "mirror"]:
        return jsonify({"error": "mode must be 'listen' or 'mirror'"}), 400

    conversation = storage.create_conversation(user_id, mode)
    return jsonify({"data": conversation}), 201


@echo_bp.get("/conversations/<conversation_id>")
def get_conversation(conversation_id: str):
    """获取对话会话详情"""
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    # 获取对话消息
    messages = storage.get_conversation_messages(conversation_id)
    conversation["messages"] = messages

    return jsonify({"data": conversation})


@echo_bp.get("/users/<user_id>/conversations")
def get_user_conversations(user_id: str):
    """获取用户的所有对话"""
    conversations = storage.get_user_conversations(user_id)
    return jsonify({"data": conversations})


@echo_bp.post("/conversations/<conversation_id>/messages")
def send_message(conversation_id: str):
    """发送消息并获取AI回复"""
    log(f"[API] 收到消息请求，conversation_id={conversation_id}")
    data = request.get_json() or {}
    log(f"[API] 请求数据: {data}")
    
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        log(f"[ERROR] Conversation {conversation_id} not found")
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json() or {}
    user_message = data.get("content", "").strip()
    log(f"[API] 消息内容: {user_message}, 长度: {len(user_message)}")
    log(f"[DEBUG] User message: {user_message}")

    if not user_message:
        return jsonify({"error": "content is required"}), 400

    current_mode = conversation["mode"]
    log(f"[DEBUG] Current mode: {current_mode}")

    # 保存用户消息（带上当前模式）
    user_msg = storage.add_message(conversation_id, "user", user_message, current_mode)
    log(f"[DEBUG] User message saved: {user_msg}")

    # 获取当前模式下的对话历史（模式隔离）
    mode_messages = storage.get_conversation_messages_by_mode(conversation_id, current_mode)
    current_mode_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in mode_messages[:-1]  # 排除刚添加的消息
    ]

    # 获取用户所有消息（用于镜像模式人格建模）
    user_all_messages = None
    if current_mode == "mirror":
        all_msgs = storage.get_user_all_messages(conversation["user_id"])
        user_all_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in all_msgs
        ]

    # 生成AI回复
    log(f"[DEBUG] Generating reply for mode={current_mode}, message={user_message[:30]}...")
    log(f"[DEBUG] Mode history length: {len(current_mode_history)}")
    
    ai_reply = generate_echo_reply(
        mode=current_mode,
        user_message=user_message,
        conversation_history=[],  # 已弃用参数
        user_all_messages=user_all_messages,
        current_mode_messages=current_mode_history,
    )

    log(f"[DEBUG] AI reply: {ai_reply}")

    if not ai_reply:
        log("[ERROR] AI reply is None or empty!")
        return jsonify({"error": "Failed to generate reply"}), 500

    # 保存AI回复（带上当前模式）
    assistant_msg = storage.add_message(conversation_id, "assistant", ai_reply, current_mode)
    log(f"[DEBUG] Assistant message saved: {assistant_msg}")

    result = {
        "data": {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
        }
    }
    log(f"[DEBUG] Returning result: {result}")
    
    return jsonify(result)


@echo_bp.patch("/conversations/<conversation_id>/mode")
def switch_mode(conversation_id: str):
    """切换对话模式（倾听/镜像）"""
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json() or {}
    new_mode = data.get("mode")

    if new_mode not in ["listen", "mirror"]:
        return jsonify({"error": "mode must be 'listen' or 'mirror'"}), 400

    success = storage.update_conversation_mode(conversation_id, new_mode)
    if not success:
        return jsonify({"error": "Failed to update mode"}), 500

    updated_conversation = storage.get_conversation(conversation_id)
    return jsonify({"data": updated_conversation})


@echo_bp.get("/users/<user_id>/profile")
def get_user_profile(user_id: str):
    """获取用户人格画像"""
    profile = storage.get_profile(user_id)
    
    if not profile:
        # 如果没有画像，尝试生成
        user_messages = storage.get_user_all_messages(user_id)
        user_msg_list = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in user_messages
        ]
        profile_data = generate_profile_summary(user_msg_list)
        
        if profile_data and profile_data.get("status") == "available":
            profile = storage.save_profile(user_id, profile_data)
        else:
            return jsonify({"data": profile_data})
    
    return jsonify({"data": profile})


@echo_bp.post("/users/<user_id>/profile/refresh")
def refresh_user_profile(user_id: str):
    """刷新用户人格画像"""
    user_messages = storage.get_user_all_messages(user_id)
    user_msg_list = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in user_messages
    ]
    
    profile_data = generate_profile_summary(user_msg_list)
    
    if not profile_data:
        return jsonify({"error": "Failed to generate profile"}), 500
    
    profile = storage.save_profile(user_id, profile_data)
    return jsonify({"data": profile})

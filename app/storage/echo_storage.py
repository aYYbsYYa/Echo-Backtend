import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from .json_repository import JsonRepository


class EchoStorage:
    """灵笺数据存储层"""

    def __init__(self, data_dir: Path):
        self.conversations_repo = JsonRepository(data_dir / "echo_conversations.json")
        self.messages_repo = JsonRepository(data_dir / "echo_messages.json")
        self.profiles_repo = JsonRepository(data_dir / "echo_profiles.json")

    def create_conversation(self, user_id: str, mode: str = "listen") -> dict[str, Any]:
        """创建新对话会话"""
        conversation = {
            "id": secrets.token_hex(8),
            "user_id": user_id,
            "mode": mode,  # listen 或 mirror
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return self.conversations_repo.append(conversation)

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """获取对话会话"""
        return self.conversations_repo.find(conversation_id)

    def get_user_conversations(self, user_id: str) -> list[dict[str, Any]]:
        """获取用户的所有对话"""
        conversations = self.conversations_repo.all()
        return [c for c in conversations if c["user_id"] == user_id]

    def update_conversation_mode(self, conversation_id: str, mode: str) -> bool:
        """切换对话模式"""
        conversations = self.conversations_repo.all()
        for conv in conversations:
            if conv["id"] == conversation_id:
                conv["mode"] = mode
                conv["updated_at"] = datetime.utcnow().isoformat()
                self.conversations_repo.replace_all(conversations)
                return True
        return False

    def add_message(
        self, conversation_id: str, role: str, content: str, mode: str = None
    ) -> dict[str, Any]:
        """添加消息到对话"""
        # 获取当前对话的模式
        if mode is None:
            conv = self.get_conversation(conversation_id)
            mode = conv["mode"] if conv else "listen"
        
        message = {
            "id": secrets.token_hex(8),
            "conversation_id": conversation_id,
            "role": role,  # user 或 assistant
            "content": content,
            "mode": mode,  # 记录消息所属的模式
            "timestamp": datetime.utcnow().isoformat(),
        }
        # 更新对话的最后更新时间
        conversations = self.conversations_repo.all()
        for conv in conversations:
            if conv["id"] == conversation_id:
                conv["updated_at"] = message["timestamp"]
                self.conversations_repo.replace_all(conversations)
                break
        return self.messages_repo.append(message)

    def get_conversation_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """获取对话的所有消息"""
        messages = self.messages_repo.all()
        return [m for m in messages if m["conversation_id"] == conversation_id]

    def get_conversation_messages_by_mode(
        self, conversation_id: str, mode: str
    ) -> list[dict[str, Any]]:
        """获取对话中特定模式下的消息（用于模式隔离的上下文）"""
        messages = self.messages_repo.all()
        return [
            m
            for m in messages
            if m["conversation_id"] == conversation_id and m.get("mode") == mode
        ]

    def get_user_all_messages(self, user_id: str) -> list[dict[str, Any]]:
        """获取用户所有对话的消息（用于人格建模）"""
        conversations = self.get_user_conversations(user_id)
        conversation_ids = {c["id"] for c in conversations}
        messages = self.messages_repo.all()
        return [m for m in messages if m["conversation_id"] in conversation_ids]

    def save_profile(self, user_id: str, profile_data: dict[str, Any]) -> dict[str, Any]:
        """保存用户人格画像"""
        profiles = self.profiles_repo.all()
        existing = None
        for p in profiles:
            if p["user_id"] == user_id:
                existing = p
                break

        if existing:
            existing["profile_data"] = profile_data
            existing["updated_at"] = datetime.utcnow().isoformat()
            self.profiles_repo.replace_all(profiles)
            return existing
        else:
            profile = {
                "id": secrets.token_hex(8),
                "user_id": user_id,
                "profile_data": profile_data,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            return self.profiles_repo.append(profile)

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        """获取用户人格画像"""
        profiles = self.profiles_repo.all()
        for p in profiles:
            if p["user_id"] == user_id:
                return p
        return None

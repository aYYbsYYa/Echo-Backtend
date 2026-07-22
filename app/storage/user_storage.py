from app.config import Config

from .json_repository import JsonRepository


class UserStorage(JsonRepository):
    def __init__(self):
        super().__init__(Config.DATA_DIR / "users.json")

    def upsert(self, user: dict) -> dict:
        users = self.all()
        existing = next((item for item in users if item["id"] == user["id"]), None)
        if existing:
            return existing
        users.append(user)
        self.replace_all(users)
        return user

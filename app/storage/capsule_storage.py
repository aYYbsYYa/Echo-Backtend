from app.config import Config

from .json_repository import JsonRepository


class CapsuleStorage(JsonRepository):
    def __init__(self):
        super().__init__(Config.DATA_DIR / "capsules.json")

from app.config import Config

from .json_repository import JsonRepository


class BottleStorage(JsonRepository):
    def __init__(self):
        super().__init__(Config.DATA_DIR / "bottles.json")

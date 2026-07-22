from app.config import Config

from .json_repository import JsonRepository


class PlaneStorage(JsonRepository):
    def __init__(self):
        super().__init__(Config.DATA_DIR / "planes.json")

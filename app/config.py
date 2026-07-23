import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
    PORT = int(os.getenv("PORT", "3000"))
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_API_URL = os.getenv("AI_API_URL", "")
    AI_MODEL = os.getenv("AI_MODEL", "")
    SENSE_VOICE_MODEL_DIR = BASE_DIR / os.getenv(
        "SENSE_VOICE_MODEL_DIR", "models/sense-voice"
    )
    SENSE_VOICE_THREADS = max(1, int(os.getenv("SENSE_VOICE_THREADS", "4")))
    UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "data/uploads")
    MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", str(5 * 1024 * 1024)))
    JSON_FILES = ("users", "bottles", "planes", "comments", "likes")

    @classmethod
    def ensure_data_files(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        for name in cls.JSON_FILES:
            path = cls.DATA_DIR / f"{name}.json"
            if not path.exists():
                path.write_text("[]\n", encoding="utf-8")

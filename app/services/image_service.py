from pathlib import Path
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from app.config import Config


class ImageUploadError(ValueError):
    pass


IMAGE_SIGNATURES = {
    "jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    "webp": lambda data: len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}


def save_image(uploaded: FileStorage | None) -> str | None:
    if uploaded is None or not uploaded.filename:
        return None

    extension = Path(uploaded.filename).suffix.lower().lstrip(".")
    if extension == "jpeg":
        extension = "jpg"
    if extension not in IMAGE_SIGNATURES:
        raise ImageUploadError("图片仅支持 JPEG、PNG、WebP 或 GIF 格式。")

    data = uploaded.read(Config.MAX_IMAGE_SIZE + 1)
    if not data:
        raise ImageUploadError("上传的图片为空。")
    if len(data) > Config.MAX_IMAGE_SIZE:
        raise ImageUploadError(f"图片大小不能超过 {Config.MAX_IMAGE_SIZE // (1024 * 1024)}MB。")
    if not IMAGE_SIGNATURES[extension](data):
        raise ImageUploadError("图片内容与文件格式不匹配。")

    Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{extension}"
    (Config.UPLOAD_DIR / filename).write_bytes(data)
    return filename


def image_url(filename: str | None) -> str | None:
    return f"/api/uploads/{filename}" if filename else None

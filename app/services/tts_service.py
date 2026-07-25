import os
import wave
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
import sherpa_onnx

from app.config import Config


class TextToSpeechError(RuntimeError):
    pass


_tts: sherpa_onnx.OfflineTts | None = None
_load_lock = Lock()
_generate_lock = Lock()


def _find_model_dir():
    root = Config.TTS_MODEL_DIR
    candidates = (root, root / "sherpa-onnx-vits-zh-ll")
    required = ("model.onnx", "tokens.txt", "lexicon.txt", "phone.fst", "date.fst", "number.fst")
    return next((path for path in candidates if all((path / name).is_file() for name in required)), None)


def _native_path(path: Path) -> str:
    try:
        return os.path.relpath(path, Path.cwd())
    except ValueError:
        return str(path)


def _get_tts() -> sherpa_onnx.OfflineTts:
    global _tts
    if _tts is not None:
        return _tts

    with _load_lock:
        if _tts is not None:
            return _tts

        model_dir = _find_model_dir()
        if model_dir is None:
            raise TextToSpeechError("灵笺语音模型未部署。")

        try:
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=_native_path(model_dir / "model.onnx"),
                lexicon=_native_path(model_dir / "lexicon.txt"),
                tokens=_native_path(model_dir / "tokens.txt"),
                dict_dir=_native_path(model_dir / "dict"),
            )
            model = sherpa_onnx.OfflineTtsModelConfig(
                vits=vits,
                num_threads=Config.TTS_THREADS,
            )
            config = sherpa_onnx.OfflineTtsConfig(
                model=model,
                rule_fsts=",".join(
                    _native_path(model_dir / name)
                    for name in ("phone.fst", "date.fst", "number.fst")
                ),
            )
            _tts = sherpa_onnx.OfflineTts(config)
        except Exception as error:
            raise TextToSpeechError("灵笺语音模型初始化失败。") from error

    return _tts


def synthesize_speech(text: str) -> bytes:
    tts = _get_tts()
    try:
        with _generate_lock:
            audio = tts.generate(text, sid=Config.TTS_SPEAKER_ID, speed=1.0)
    except Exception as error:
        raise TextToSpeechError("灵笺暂时无法开口，请稍后重试。") from error

    samples = np.asarray(audio.samples, dtype=np.float32)
    if samples.size == 0:
        raise TextToSpeechError("灵笺没有生成有效语音。")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()

    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(audio.sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()

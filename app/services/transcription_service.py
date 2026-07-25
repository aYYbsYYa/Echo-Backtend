import re
from io import BytesIO
from threading import Lock

import numpy as np
import sherpa_onnx
import soundfile as sf

from app.config import Config


class SenseVoiceError(RuntimeError):
    """Raised when local SenseVoice transcription cannot be completed."""


_recognizer: sherpa_onnx.OfflineRecognizer | None = None
_load_lock = Lock()
_decode_lock = Lock()


def _get_recognizer() -> sherpa_onnx.OfflineRecognizer:
    global _recognizer

    if _recognizer is not None:
        return _recognizer

    with _load_lock:
        if _recognizer is not None:
            return _recognizer

        model_dirs = (
            Config.SENSE_VOICE_MODEL_DIR,
            Config.BASE_DIR / "models",
        )
        model_names = (
            "model.int8.onnx",
            "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8.onnx",
        )
        model_pair = next(
            (
                (directory / name, directory / "tokens.txt")
                for directory in model_dirs
                for name in model_names
                if (directory / name).is_file() and (directory / "tokens.txt").is_file()
            ),
            None,
        )
        if model_pair is None:
            raise SenseVoiceError("SenseVoice 模型或词表文件未部署。")
        model, tokens = model_pair

        try:
            _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(model),
                tokens=str(tokens),
                use_itn=True,
                num_threads=Config.SENSE_VOICE_THREADS,
                debug=False,
            )
        except Exception as error:
            raise SenseVoiceError("SenseVoice 模型初始化失败。") from error

    return _recognizer


def _clean_text(text: str) -> str:
    return re.sub(r"<\|[^|>]+\|>", "", text).strip()


def transcribe_audio(audio: bytes) -> str:
    """Transcribe a WAV byte stream using the local SenseVoice ONNX model."""
    try:
        waveform, sample_rate = sf.read(
            BytesIO(audio), dtype="float32", always_2d=False
        )
    except Exception as error:
        raise SenseVoiceError("无法读取音频。") from error

    if not isinstance(waveform, np.ndarray) or waveform.size == 0:
        raise SenseVoiceError("音频为空。")
    if waveform.ndim > 1:
        waveform = waveform[:, 0]

    recognizer = _get_recognizer()
    try:
        with _decode_lock:
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, waveform)
            recognizer.decode_stream(stream)
            text = stream.result.text
    except Exception as error:
        raise SenseVoiceError("SenseVoice 转写失败。") from error

    cleaned = _clean_text(text)
    if not cleaned:
        raise SenseVoiceError("未识别到有效语音内容。")
    return cleaned

import shutil
import subprocess


class AudioConversionError(ValueError):
    pass


def convert_audio_to_wav(data: bytes) -> bytes:
    if not data:
        raise AudioConversionError("录音数据为空。")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioConversionError("服务端缺少 ffmpeg，暂时无法处理录音。")

    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "wav",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "pipe:1",
        ],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode or not completed.stdout:
        raise AudioConversionError("无法读取该录音，请换一种音频格式后重试。")
    return completed.stdout

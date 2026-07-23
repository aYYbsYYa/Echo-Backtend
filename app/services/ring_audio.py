import shutil
import struct
import subprocess
import wave
from io import BytesIO


SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_SIZE = 320
MAX_PACKET_SIZE = 540


class RingAudioError(ValueError):
    pass


def _ogg_crc(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value << 24
        for _ in range(8):
            crc = (((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else (crc << 1)) & 0xFFFFFFFF
    return crc


def _ogg_page(packet: bytes, header_type: int, granule: int, serial: int, sequence: int) -> bytes:
    lacing = []
    remaining = len(packet)
    while remaining >= 255:
        lacing.append(255)
        remaining -= 255
    lacing.append(remaining)
    if len(lacing) > 255:
        raise RingAudioError("单个 Speex 数据包过大")
    header = bytearray(
        struct.pack(
            "<4sBBQIIIB",
            b"OggS",
            0,
            header_type,
            granule,
            serial,
            sequence,
            0,
            len(lacing),
        )
    )
    page = bytes(header) + bytes(lacing) + packet
    return page[:22] + struct.pack("<I", _ogg_crc(page)) + page[26:]


def _packetized_speex(data: bytes) -> list[bytes]:
    packets: list[bytes] = []
    offset = 0
    while offset + 2 <= len(data):
        size = struct.unpack_from("<H", data, offset)[0]
        if not size:
            break
        if size > MAX_PACKET_SIZE or offset + 2 + size > len(data):
            raise RingAudioError("戒指录音的 Speex 帧格式无效")
        packets.append(data[offset + 2 : offset + 2 + size])
        offset += 2 + size
    if not packets or any(byte not in (0, 0xFF) for byte in data[offset:]):
        raise RingAudioError("戒指录音中没有有效的 Speex 帧")
    return packets


def _build_ogg_speex(packets: list[bytes]) -> bytes:
    version = b"speex-1.2.1" + b"\x00" * (20 - len(b"speex-1.2.1"))
    header = struct.pack(
        "<8s20s13i",
        b"Speex   ",
        version,
        1,
        80,
        SAMPLE_RATE,
        1,
        4,
        1,
        -1,
        FRAME_SIZE,
        0,
        1,
        0,
        0,
        0,
    )
    vendor = b"yeve-echo"
    comments = struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)
    pages = [
        _ogg_page(header, 2, 0, 0x564F5247, 0),
        _ogg_page(comments, 0, 0, 0x564F5247, 1),
    ]
    granule = 0
    for index, packet in enumerate(packets):
        granule += FRAME_SIZE
        pages.append(_ogg_page(packet, 4 if index == len(packets) - 1 else 0, granule, 0x564F5247, index + 2))
    return b"".join(pages)


def _wav_from_pcm(pcm: bytes) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return output.getvalue()


def decode_ring_audio(data: bytes) -> bytes:
    if not data:
        raise RingAudioError("录音数据为空")
    try:
        packets = _packetized_speex(data)
    except RingAudioError:
        if len(data) < 20 or len(data) % 20:
            raise
        packets = [data[offset : offset + 20] for offset in range(0, len(data), 20)]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RingAudioError("服务端缺少 ffmpeg，暂时无法解码戒指录音")
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "ogg", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
        input=_build_ogg_speex(packets),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RingAudioError(f"戒指录音解码失败: {detail[:300]}")
    return _wav_from_pcm(completed.stdout)

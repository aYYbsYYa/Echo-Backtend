from flask import Blueprint, jsonify, request

from app.services.ring_audio import RingAudioError, decode_ring_audio
from app.services.transcription_service import SenseVoiceError, transcribe_audio


audio_bp = Blueprint("audio", __name__)


@audio_bp.post("/transcriptions")
def transcribe_ring_audio():
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify({"error": {"message": "缺少戒指录音文件。"}}), 400

    try:
        wav = decode_ring_audio(uploaded.read())
        text = transcribe_audio(wav)
    except RingAudioError as error:
        return jsonify({"error": {"message": str(error)}}), 422
    except SenseVoiceError as error:
        return jsonify({"error": {"message": str(error)}}), 503

    return jsonify({"data": {"text": text}})

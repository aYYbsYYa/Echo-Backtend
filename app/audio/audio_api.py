from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file

from app.services.audio_conversion import AudioConversionError, convert_audio_to_wav
from app.services.ring_audio import RingAudioError, decode_ring_audio
from app.services.transcription_service import SenseVoiceError, transcribe_audio
from app.services.tts_service import TextToSpeechError, synthesize_speech


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


@audio_bp.post("/speech")
def create_speech():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": {"message": "缺少需要朗读的文字。"}}), 400
    text = text.strip()
    if len(text) > 500:
        return jsonify({"error": {"message": "单次朗读不能超过 500 字。"}}), 400

    try:
        wav = synthesize_speech(text)
    except TextToSpeechError as error:
        return jsonify({"error": {"message": str(error)}}), 503

    return send_file(
        BytesIO(wav),
        mimetype="audio/wav",
        download_name="lingjian-reply.wav",
        max_age=0,
    )


@audio_bp.post("/transcriptions/upload")
def transcribe_uploaded_audio():
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify({"error": {"message": "缺少录音文件。"}}), 400

    data = uploaded.read(current_app.config["MAX_AUDIO_SIZE"] + 1)
    if len(data) > current_app.config["MAX_AUDIO_SIZE"]:
        return jsonify({"error": {"message": "录音文件不能超过 10MB。"}}), 413

    try:
        wav = convert_audio_to_wav(data)
        text = transcribe_audio(wav)
    except AudioConversionError as error:
        return jsonify({"error": {"message": str(error)}}), 422
    except SenseVoiceError as error:
        return jsonify({"error": {"message": str(error)}}), 503

    return jsonify({"data": {"text": text}})

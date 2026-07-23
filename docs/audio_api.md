# 戒指音频转写 API

## `POST /api/audio/transcriptions`

接收前端通过 Web Bluetooth 从戒指组装出的原始录音帧。服务端将
packetized Speex 解码为 WAV 后，使用本地的 SenseVoice ONNX 模型转写；
整个过程不调用外部语音识别 API。

请求使用 `multipart/form-data`：

```text
file: ring-recording.bin
```

成功响应：

```json
{"data":{"text":"语音转写后的文字"}}
```

服务端配置：

```env
SENSE_VOICE_MODEL_DIR=models/sense-voice
SENSE_VOICE_THREADS=4
```

`SENSE_VOICE_MODEL_DIR` 必须包含 `model.int8.onnx` 与 `tokens.txt`。
当前仓库已在 `models/sense-voice/` 放置这两个文件，且该目录已被 Git
忽略，避免将约 240 MB 的模型提交到仓库。

服务端镜像仍需要 `ffmpeg`，用于将戒指的 packetized Speex 数据解码为 WAV。

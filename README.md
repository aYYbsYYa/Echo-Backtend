# Yeve Echo Backend

Yeve Echo 是一个匿名文字漂流社区 Demo API。服务端使用 Flask 和 JSON 文件持久化，
便于后续替换为数据库。

## 技术栈

- Python 3.12+
- Flask
- JSON repository storage
- 本地 SenseVoice ONNX 语音转写
- Docker

## 配置

复制 `.env.example` 为 `.env` 后按需修改：

```env
PORT=3000
DATA_DIR=data
AI_API_KEY=
AI_API_URL=
AI_MODEL=
SENSE_VOICE_MODEL_DIR=models/sense-voice
SENSE_VOICE_THREADS=4
UPLOAD_DIR=data/uploads
MAX_IMAGE_SIZE=5242880
```

`AI_*` 用于生成漂流瓶或纸飞机发布后的开发组回信。`AI_API_URL` 可填写完整的
`/v1/chat/completions` 地址，也可填写 OpenAI-compatible 服务的 host 或 `/v1`
base URL。未配置或调用失败时，内容仍可正常发布，但不会生成固定模板回信。

戒指语音转写使用本地 SenseVoice ONNX 模型，不需要额外的语音 API 密钥。模型目录
由 `SENSE_VOICE_MODEL_DIR` 指定，默认是 `models/sense-voice`；目录中需包含
`model.int8.onnx` 和 `tokens.txt`。详见 `docs/audio_api.md`。

## 本地开发

```bash
pip install -r requirements.txt
python main.py
```

服务默认监听 `http://localhost:3000`。

## Docker

```bash
docker build -t yeve-echo-backend .
docker run --rm -p 3000:3000 -v yeve-echo-data:/app/data yeve-echo-backend
```

镜像会安装 `ffmpeg`，用于解码戒指上传的 packetized Speex 音频。

## API

- `POST /api/users` 创建或读取匿名身份
- `POST /api/bottles` 发布漂流瓶
- `GET /api/bottles/discover` 捞取漂流瓶
- `POST /api/planes` 扔纸飞机
- `GET /api/planes/discover` 接住纸飞机
- `POST /api/audio/transcriptions` 将戒指录音转写为文本

完整请求和响应示例见 `docs/`。

## 数据结构

运行时在 `data/` 维护以下集合：

- `users.json`：不可编辑的匿名身份
- `bottles.json`：漂流瓶、标签、浏览量与开发组回信
- `planes.json`：纸飞机、落点场景、浏览量与开发组回信
- `likes.json`：用户到内容的点赞关系
- `comments.json`：评论记录

所有文件访问都封装在 `app/storage/`，路由层不直接操作 JSON 文件。

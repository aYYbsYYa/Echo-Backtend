# Yeve Echo Backend

Yeve Echo 是一个匿名文字漂流社区的 Demo API。用户没有账户和密码，前端将浏览器生成的匿名身份传给 API；服务端以 JSON 文件持久化内容，便于后续替换为数据库实现。

## 技术栈

- Python 3.12+
- Flask
- JSON repository storage
- Docker

## 配置

复制 `.env.example` 为 `.env` 后按需修改：

```env
PORT=3000
DATA_DIR=data
AI_API_KEY=
AI_API_URL=
AI_MODEL=
```

`AI_*` 为预留配置。Demo 当前使用本地审核兜底，因此不配置密钥也可工作。

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

## API

- `POST /api/users` 创建或读取匿名身份
- `POST /api/bottles` 发布漂流瓶
- `GET /api/bottles/discover` 捞取漂流瓶
- `POST /api/planes` 扔纸飞机
- `GET /api/planes/discover` 接住纸飞机
- `POST /api/ai/moderate` 审核文本

完整请求和返回示例见 `docs/`。

## 数据结构

运行时在 `data/` 维护以下集合：

- `users.json`：不可编辑的匿名身份
- `bottles.json`：漂流瓶、标签、浏览量与官方回信
- `planes.json`：纸飞机、落点场景与浏览量
- `likes.json`：用户到内容的点赞关系
- `comments.json`：仅由作者查看的留言

所有文件访问封装在 `app/storage/`，路由层不直接操作 JSON 文件。

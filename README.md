# Echo-Backtend · Yeve Echo 服务端

> 社交是向外的喧嚣，Echo 是向内的回响。

Yeve Echo 的接入层服务，基于 **Flask + JSON 文件存储 + 本地 ONNX 语音模型**，为前端（[Echo-Frontend](https://github.com/aYYbsYYa/Echo-Frontend) / [Echo-Frontend-v2](https://github.com/aYYbsYYa/Echo-Frontend-v2)）提供浮笺、飞笺、心笺、灵笺、Agent to Agent 与语音转写/合成的全部能力。

服务端刻意保持轻薄：它只做**数据存取、AI 编排与内容安全兜底**，把「不被围观」的产品规则实打实地写进接口——互动数据只随发布者本人的请求返回，心笺未到期时连配图都不可访问。

- 在线演示：<https://echo.yeve.top>
- 健康检查：<https://echoapi.yyoo.fun/api/health>（本地为 `http://localhost:3000/api/health`）
- 内置体验页：`http://localhost:3000/echo_demo.html`

---

## 一、项目介绍

### 1.1 职责边界

| 能力 | 说明 |
| :--- | :--- |
| 匿名身份 | 无手机号、无邮箱、无密码；`POST /api/users` 生成 `id / nickname / birthday / gender`，user id 即凭证 |
| 浮笺 / 飞笺 | 发布（可带图）、完全随机发现（排除本人内容）、详情、点赞切换、留言、我的发布 |
| 心笺 | 时间胶囊封存与到期解锁；预设 1 个月 / 3 个月 / 半年 / 1 年，自定义范围 60 秒 ~ 10 年；未到期返回 `423`，配图接口同样拒绝 |
| 灵笺 | 倾听 / 镜像两种模式的人格镜像对话、会话历史、长期表达画像生成与刷新 |
| Agent to Agent | 画像 → 可解释匹配 → 双 Agent 多轮对话（同步与流式两条链）→ 共鸣回响分析 → 历史回响与彻底删除 |
| 语音 | ASR（SenseVoice，支持浏览器录音与智能戒指 Speex 流）与 TTS（sherpa-onnx VITS 中文）全部本地推理，不外发音频 |
| 演示数据 | `demo_seed` 一键重置为评委可复现的演示状态 |

### 1.2 「私密互动」在服务端如何落地

- `discover` 类接口在查询阶段就排除发布者自己的内容，并只累加浏览量；
- `likes` / `comments` 的读取只允许发生在 `GET /api/bottles/mine/:user_id` 这条「本人视角」链路上，任何第三方查询接口都不返回互动明细；
- 心笺到期前，`GET /api/capsules/:id/image` 直接拒绝，避免通过图片间接泄露内容；
- Agent 对话记录匿名呈现，且提供 `DELETE /api/agent/dialogues/:id` 永久删除。

---

## 二、技术架构

### 2.1 技术栈

| 层次 | 选型 | 版本 | 说明 |
| :--- | :--- | :--- | :--- |
| 语言 | Python | 3.12（镜像 `python:3.12-slim`） | 最低 3.10 可运行 |
| Web 框架 | Flask | `3.1.3` | 7 个 Blueprint 按业务域拆分 |
| WSGI 工具 | Werkzeug | `3.1.8` | 静态上传文件服务与开发服务器 |
| 大模型接入 | 标准库 `urllib.request` | — | **不引入任何 SDK**，直连 OpenAI-compatible `/v1/chat/completions` |
| 语音识别 | sherpa-onnx | `1.13.4` | SenseVoice 多语种模型，本地 int8 推理 |
| 语音合成 | sherpa-onnx | `1.13.4` | VITS 中文模型（`sherpa-onnx-vits-zh-ll`） |
| 音频处理 | `soundfile 0.14.0` + `ffmpeg` | — | Speex/OGG/WAV 解码与重采样 |
| 数值 | numpy | `2.2.6` | 音频张量处理 |
| 配置 | python-dotenv | `1.2.2` | `.env` 加载 |
| 存储 | JSON 文件 | 标准库 | 无数据库依赖，便于替换为真实 DB |
| 测试 | `unittest` | 标准库 | 42 个自动化用例 |
| 容器 | Docker | `Dockerfile` | 安装 ffmpeg，`EXPOSE 3000`，`CMD ["python","main.py"]` |

### 2.2 目录结构

```
main.py                     # 入口：create_app() + 路由清单打印
app/
├─ __init__.py              # create_app：加载配置、建数据文件、注册 7 个蓝图、全局 CORS
├─ config.py                # 全部环境变量集中读取
├─ user/                    # 匿名身份
├─ bottle/                  # 浮笺
├─ plane/                   # 飞笺
├─ capsule/                 # 心笺（时间胶囊）
├─ echo/                    # 灵笺（人格镜像对话）
├─ agent/                   # Agent to Agent（含 demo_data 演示人格池）
├─ audio/                   # 语音转写与合成接口
├─ demo_seed/               # 演示数据种子与重置
├─ services/                # 9 个服务：ai_service / agent_service / echo_service /
│                           #   transcription_service / tts_service / ring_audio /
│                           #   audio_conversion 等
└─ storage/                 # JsonRepository + 5 个薄封装
data/                       # 运行时 JSON 集合与上传文件（不入库）
models/                     # 本地 ONNX 语音模型（体积过大，不入库）
tests/                      # unittest 用例与 HTTP 冒烟脚本
docs/                       # 模块 API 文档、评委演示数据说明、设计稿
echo_demo.html              # 内置接口体验页
```

### 2.3 存储设计

- 12 个集合（`app/config.py:30-43`）：`users / bottles / planes / comments / likes / capsules / echo_conversations / echo_messages / echo_profiles / agent_profiles / agent_matches / agent_dialogues`。
- `app/storage/json_repository.py`：按文件路径共享 `threading.Lock`，写入先落 `.tmp` 再 `os.replace` 原子改名，避免并发读写撕裂。
- `agent_matches` / `agent_dialogues` 使用 `append(max_records=100)` 滚动上限，防止演示数据无限膨胀。
- 上传的图片与胶囊配图分别落在 `data/uploads/`、`data/capsule_images/`，均被 `.gitignore` 排除。

### 2.4 接口总览

所有端点以 `/api/*` 前缀挂载（`app/__init__.py:22-28`）。

| 模块 | 方法与路径 | 要点 |
| :--- | :--- | :--- |
| 健康 | `GET /api/health` | 存活探针 |
| 静态 | `/api/uploads/<file>`、`/echo_demo.html` | 图片回源与内置体验页 |
| 身份 | `POST /api/users`、`GET /api/users/:id` | 创建/读取匿名身份 |
| 浮笺 | `POST /api/bottles`、`GET /api/bottles/discover`、`GET /api/bottles/:id`、`POST /api/bottles/:id/likes`、`POST /api/bottles/:id/comments`、`GET /api/bottles/mine/:uid` | 发布支持 JSON 或 multipart（`image` 字段，≤5MB）；发布后异步生成「开发组回信」 |
| 飞笺 | 同构的 `/api/planes/*` | 额外携带 `scene` 落点场景 |
| 心笺 | `POST /api/capsules`、`GET /api/capsules/mine/:uid`、`POST /api/capsules/:id/open`、`GET /api/capsules/:id/image` | `mood` 六标签；配图 base64 ≤1.5MB；未到期 `423` |
| 灵笺 | `POST /api/echo/conversations`（`mode=listen\|mirror`）、`GET /api/echo/conversations/:id`、`GET /api/echo/users/:uid/conversations`、`POST /api/echo/conversations/:id/messages`、`PATCH /api/echo/conversations/:id/mode`、`GET /api/echo/users/:uid/profile`、`POST /api/echo/users/:uid/profile/refresh` | 长期表达 ≥5 条后才生成画像 |
| 灵魂回响 | `GET /api/agent/profile`、`POST /api/agent/match`（`limit` 1–3）、`POST /api/agent/dialogue`、`POST /api/agent/dialogue/stream`、`GET /api/agent/dialogues`、`DELETE /api/agent/dialogues/:id` | 流式接口返回 **NDJSON**；带进程内滑动窗口限流（`agent_api.py:37-53`） |
| 语音 | `POST /api/audio/transcriptions`（戒指 Speex）、`POST /api/audio/transcriptions/upload`（通用音频，≤10MB）、`POST /api/audio/speech`（≤500 字，返回 WAV） | 全部本地推理 |

完整的请求/响应示例见 `docs/`。

---

## 三、AI 技术方案

### 3.1 选型理由

| 决策 | 理由 |
| :--- | :--- |
| 用 OpenAI-compatible 协议而非厂商 SDK | 产品需要的是**可替换的推理后端**：改三个环境变量即可在 DeepSeek、OpenAI、通义千问兼容模式等任意服务间切换；同时避免为几个 HTTP 调用引入重型依赖，保持 `requirements.txt` 精简 |
| 用标准库 `urllib` 直连 | 减少供应链与体积；请求体、超时、错误码全部显式可控，便于统一兜底 |
| 语音全部本地推理（sherpa-onnx） | 情绪倾诉内容高度敏感，**音频不出机器**；同时零调用成本、无网络抖动 |
| JSON 文件而非数据库 | 黑客松场景下追求可读与可迁移；访问已收敛到 `app/storage/`，替换为真实数据库只需改一层 |

### 3.2 集成方式

```
前端视图 ──HTTP/NDJSON──► Flask 蓝图
                              └─ app/services/*
                                   ├─ ai_service.py         统一 LLM 客户端（urllib → /v1/chat/completions）
                                   ├─ echo_service.py       灵笺：倾听 / 镜像双模式
                                   ├─ agent_service.py      A2A：画像 / 匹配 / 双 Agent 对话 / 回响
                                   ├─ transcription_service.py  SenseVoice ASR
                                   └─ tts_service.py        sherpa-onnx VITS TTS
```

`services/ai_service.py:16-55` 会把 `AI_API_URL` 自动规范化为完整的 `/v1/chat/completions` 地址（允许填 host、`/v1` 或完整 URL）；**任何失败都返回 `None`，由各业务模块走模板兜底**，保证 AI 不可用时产品功能不中断。

### 3.3 Prompt 工程

| 用途 | 位置 | 设计要点 |
| :--- | :--- | :--- |
| 开发组回信 | `services/ai_service.py:8` | 短促、克制，不复述用户原话 |
| 灵魂画像 | `services/agent_service.py:58-86` `PROFILE_SYSTEM_PROMPT` | 指定字段 schema，要求输出 JSON；禁止复述原话片段 |
| Agent 拟人表达 | 同上 `AGENT_MESSAGE_SYSTEM_PROMPT` | 8 条表达规则 + 35~75 字长度约束，压制「AI 腔」 |
| 回响分析 | 同上 `ECHO_SYSTEM_PROMPT` | 只提炼共同关切与情绪重合点，不推断身份 |
| 灵笺倾听/镜像 | `services/echo_service.py:25-124` | 分模式分级回复长度；禁止动作描写与括号旁白 |

**结构化输出约束**：`_parse_json_object` 先剥离 Markdown 代码块围栏，`_valid_profile_payload` 再校验字段与取值，任一不合格立即回退到模板画像——这是输出可控性的关键一环。

### 3.4 Agent 工作流

1. **画像**：真实用户从 `echo_profiles`（灵笺长期表达）提炼；少于 5 条消息时提示先去灵笺表达，避免凭空捏造人格。
2. **匹配**：`score = 62 + 18×兴趣重叠 + 10×情绪重叠 + 10×价值观重叠`（封顶 100，`agent_service.py:366-458`）；标签先经 `TAG_SEMANTIC_GROUPS` 做同义归一（语义匹配权重 0.8），因此「温暖技术」与「有温度的技术」能命中；`reason` 由共同标签直接生成，**排序可被人工复核**。
3. **对话**：3 轮 × 2 方共 6 句，由 `_dialogue_messages` 逐句生成、`_complete_dialogue` 收尾，最后由 Echo 模型给出共鸣分析。
4. **流式**：`POST /api/agent/dialogue/stream` 以 NDJSON 逐条推送，客户端断开即中止，**中断的对话不会落库**（避免半截记录污染画像）。

> 本项目未使用 RAG / Function Calling / MCP；智能体能力体现在**双 Agent 多轮编排 + 可解释匹配 + 分级兜底**上。

### 3.5 内容安全与可控性

| 风险 | 机制 | 位置 |
| :--- | :--- | :--- |
| 模型泄露联系方式 | `CONTACT_PATTERN`（邮箱 / URL / 电话）+ `CONTACT_TERMS`（微信、QQ、私聊等 12 个词）统一过滤 | `agent_service.py` `_safe_model_text` |
| 暴露真实身份 | `PRIVATE_IDENTITY_PATTERN` 拦截姓名、年龄、住址 | 同上 |
| 画像泄露原始表达 | `_history_fragments` 滑窗禁词，禁止复述用户原话片段 | 同上 |
| 复读机式重复 | `_repeats_conversation` 用 `SequenceMatcher` 阈值 0.86 判定重复 | 同上 |
| 「AI 腔」套话 | `_sounds_like_agent_copy` 命中 13 个套话黑名单即重写 | 同上 |
| 兜底不重复 | 兜底模板提供 7 个变体，避免连续两轮出现同一句 | 同上 |
| 灵笺回复失控 | 倾听模式 >120 字截断到句末标点；清除括号动作语 | `echo_service.py:281-307` |
| 接口滥用 | Agent 路由进程内滑动窗口限流 | `agent_api.py:37-53` |

### 3.6 语音链路

- **ASR**：`services/transcription_service.py` 使用 sherpa-onnx `OfflineRecognizer` 加载 SenseVoice（zh/en/ja/ko/yue，int8），模型目录依次探测 `SENSE_VOICE_MODEL_DIR` 与 `models/`。
- **戒指音频**：`services/ring_audio.py` 解析自定义分帧 Speex，经 ffmpeg 转 OGG/WAV 后送 ASR。
- **TTS**：`services/tts_service.py` 加载 VITS 中文模型（默认 `TTS_SPEAKER_ID=2`），把 Agent 回复合成 WAV 返回前端播放。
- **模型文件不入库**（合计约 370MB），需自行下载放置：
  - `models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8.onnx` 与 `models/tokens.txt`
  - `models/sherpa-onnx-vits-zh-ll/`（`model.onnx`、`tokens.txt`、词典与音素文件）
  - 来源为 sherpa-onnx 官方模型仓库（k2-fsa/sherpa-onnx 的 Releases 与 Hugging Face 模型页），下载后保持上述目录名即可，无需改代码。

---

## 四、安装与运行

### 4.1 环境要求

- Python 3.10+（推荐 3.12，与 Docker 镜像一致）
- ffmpeg（仅在需要解码戒指 Speex 音频时必需，通用语音与文本功能不依赖）
- Node 前端仓库见各自 README

### 4.2 安装与启动

```bash
# 1. 虚拟环境
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. 依赖
pip install -r requirements.txt

# 3. 配置
cp .env.example .env               # Windows: copy .env.example .env

# 4. 启动（默认 3000 端口，控制台会打印全部路由）
python main.py
```

`http://localhost:3000/echo_demo.html` 是内置体验页，可直接逐个接口点验，无需前端。

### 4.3 环境变量

| 变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `FLASK_ENV` | `development` | `development` 时开启 debug |
| `PORT` | `3000` | 监听端口 |
| `DATA_DIR` | `data` | JSON 集合目录 |
| `AI_API_KEY` | 空 | **大模型密钥，只允许写在 `.env`，仓库不收录** |
| `AI_API_URL` | 空 | OpenAI-compatible 服务地址，可填 host、`/v1` 或完整 `/v1/chat/completions` |
| `AI_MODEL` | 空 | 模型名；三者任一为空即走模板兜底，服务不报错 |
| `SENSE_VOICE_MODEL_DIR` | `models/sense-voice` | ASR 模型目录 |
| `SENSE_VOICE_THREADS` | `4` | ASR 推理线程 |
| `TTS_MODEL_DIR` | `models/sherpa-onnx-vits-zh-ll` | TTS 模型目录 |
| `TTS_THREADS` | `2` | TTS 推理线程 |
| `TTS_SPEAKER_ID` | `2` | VITS 说话人编号 |
| `UPLOAD_DIR` | `data/uploads` | 图片存储目录 |
| `MAX_IMAGE_SIZE` | `5242880` | 图片上限 5MB |
| `MAX_AUDIO_SIZE` | `10485760` | 音频上限 10MB |
| `DEMO_RESET_ON_START` | `false` | 置 `true` 时启动即重置为演示数据（评委复现建议开启） |

安全约定：`.env` 已被 `.gitignore` 忽略且从未进入任何提交历史；仓库只提供 `.env.example` 模板，其中所有密钥位为空。

### 4.4 Docker

```bash
docker build -t yeve-echo-backend .
docker run --rm -p 3000:3000 -v yeve-echo-data:/app/data yeve-echo-backend
```

镜像基于 `python:3.12-slim` 并安装 ffmpeg。语音模型不打进镜像，如需容器内语音能力，请额外挂载 `models/`。

### 4.5 测试

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

| 文件 | 类型 | 用例 | 覆盖 |
| :--- | :--- | :--- | :--- |
| `tests/test_agent_demo.py` | unittest | 28 | 画像校验、匹配可解释性与排序、双 Agent 对话、流式与中断不落库、历史删除与归属、联系方式/身份泄露拒绝、重复输出替换 |
| `tests/test_bottle_flows.py` | unittest | 10 | 发布与发现、点赞留言仅本人可见、AI 回信降级、图片校验与服务、无效 AI 地址不抛异常 |
| `tests/test_demo_seed.py` | unittest | 4 | 演示种子幂等重置与 API 暴露 |
| `tests/test_echo_api.py` | HTTP 冒烟 | 8 步 | 需服务在跑：`python tests/test_echo_api.py` |

---

## 五、代码规范

- 分层约定：**路由层只做参数校验与状态码，业务规则在 `app/services/`，持久化只在 `app/storage/`**，路由不直接读写 JSON。
- 每个业务域一个 Blueprint 包（`user / bottle / plane / capsule / echo / agent / audio`），对外前缀集中在 `app/__init__.py` 声明。
- 所有环境变量经 `app/config.py` 读取并给默认值，代码中不出现硬编码地址、密钥或绝对路径。
- 任何外部调用（LLM、模型加载）失败都必须有兜底分支，禁止把 5xx 抛给前端。
- 与前端字段同名，不做重命名映射；接口变更同步更新 `docs/`。

---

## 六、团队信息

**本次参赛队伍（传智杯）：Yeve Hoo**

| 成员 | 角色 | 分工 |
| :--- | :--- | :--- |
| 邓紫阳 | 队长 | 开发 |
| 刘艺红 | 队员 | 演示视频、PPT 与视觉物料 |

**原项目（黑客松版本）贡献者**

| 贡献者 | 分工 |
| :--- | :--- |
| aYYbsYYa | 前后端开发 |
| Speculator | 前后端开发 |
| Naije | 设计 |
| 是晞宝呀 | 设计 |

---

## 七、开发记录

- 原项目开发提交 39 次，时间跨度 2026-07-23 ~ 2026-07-25；2026-11 为本次赛项提交另加文档与安全清理类提交。完整历史保留在 `main` 分支，未做压缩、改写或 rebase，可用 `git log --follow` 逐条核对；`add-agent-to-agent-fix`、`add_aagent_to_agennt` 为 Agent to Agent 的并行开发分支。
- 主要演进：项目初始化 → 漂流瓶与纸飞机 → SenseVoice 转写 → 时间胶囊 → Soul Agent 与 Agent to Agent → 灵笺 → 演示种子 → 语音转写与合成（HEAD）。
- 本项目曾获 **百度秒哒 · 应用美学赛道 最佳交互奖**。

## 八、许可与说明

本项目为参赛作品，代码公开用于评审与学习交流。大模型 API 密钥与 ONNX 语音模型权重均不随仓库分发，需按各自官方条款自行获取与配置；服务对用户表达内容仅做本地/自有密钥下的推理，不做二次分发。

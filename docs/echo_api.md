# 灵笺 API 文档

## 概述

灵笺（Yeve Echo）是一个AI驱动的自我对话与洞察系统，提供两种对话模式：
- **倾听模式**：AI作为温暖的陪伴者，倾听并共情
- **镜像模式**：AI化身为"另一个你"，用你的思维方式回应

## API 端点

### 1. 创建对话会话

**请求**
```http
POST /api/echo/conversations
Content-Type: application/json

{
  "user_id": "string",
  "mode": "listen" | "mirror"  // 可选，默认为 "listen"
}
```

**响应**
```json
{
  "data": {
    "id": "c0aab044d78971d9",
    "user_id": "test_user_001",
    "mode": "listen",
    "created_at": "2024-01-20T10:30:00",
    "updated_at": "2024-01-20T10:30:00"
  }
}
```

---

### 2. 获取对话详情

**请求**
```http
GET /api/echo/conversations/{conversation_id}
```

**响应**
```json
{
  "data": {
    "id": "c0aab044d78971d9",
    "user_id": "test_user_001",
    "mode": "listen",
    "created_at": "2024-01-20T10:30:00",
    "updated_at": "2024-01-20T10:35:00",
    "messages": [
      {
        "id": "msg_001",
        "conversation_id": "c0aab044d78971d9",
        "role": "user",
        "content": "我最近很焦虑...",
        "timestamp": "2024-01-20T10:32:00"
      },
      {
        "id": "msg_002",
        "conversation_id": "c0aab044d78971d9",
        "role": "assistant",
        "content": "我能感受到你的焦虑...",
        "timestamp": "2024-01-20T10:32:05"
      }
    ]
  }
}
```

---

### 3. 获取用户所有对话

**请求**
```http
GET /api/echo/users/{user_id}/conversations
```

**响应**
```json
{
  "data": [
    {
      "id": "c0aab044d78971d9",
      "user_id": "test_user_001",
      "mode": "listen",
      "created_at": "2024-01-20T10:30:00",
      "updated_at": "2024-01-20T10:35:00"
    }
  ]
}
```

---

### 4. 发送消息并获取回复

**请求**
```http
POST /api/echo/conversations/{conversation_id}/messages
Content-Type: application/json

{
  "content": "我最近总是拖延，明明知道该做什么，就是不想动..."
}
```

**响应**
```json
{
  "data": {
    "user_message": {
      "id": "msg_003",
      "conversation_id": "c0aab044d78971d9",
      "role": "user",
      "content": "我最近总是拖延...",
      "timestamp": "2024-01-20T10:40:00"
    },
    "assistant_message": {
      "id": "msg_004",
      "conversation_id": "c0aab044d78971d9",
      "role": "assistant",
      "content": "我能感受到你此刻的纠结和疲惫...",
      "timestamp": "2024-01-20T10:40:05"
    }
  }
}
```

---

### 5. 切换对话模式

**请求**
```http
PATCH /api/echo/conversations/{conversation_id}/mode
Content-Type: application/json

{
  "mode": "mirror"  // "listen" 或 "mirror"
}
```

**响应**
```json
{
  "data": {
    "id": "c0aab044d78971d9",
    "user_id": "test_user_001",
    "mode": "mirror",
    "created_at": "2024-01-20T10:30:00",
    "updated_at": "2024-01-20T10:45:00"
  }
}
```

---

### 6. 获取用户人格画像

**请求**
```http
GET /api/echo/users/{user_id}/profile
```

**响应（对话充足）**
```json
{
  "data": {
    "id": "profile_001",
    "user_id": "test_user_001",
    "profile_data": {
      "status": "available",
      "message_count": 10,
      "total_words": 856,
      "traits": "- 表达详细，善于阐述想法\n- 对未来较为敏感，容易产生焦虑情绪\n- 有时会逃避行动，可能在与完美主义作斗争\n- 最近关注：工作, 自我成长"
    },
    "created_at": "2024-01-20T10:50:00",
    "updated_at": "2024-01-20T10:50:00"
  }
}
```

**响应（对话不足）**
```json
{
  "data": {
    "status": "insufficient_data",
    "message_count": 2,
    "summary": "对话量较少，暂无法生成完整的人格画像"
  }
}
```

---

### 7. 刷新用户人格画像

**请求**
```http
POST /api/echo/users/{user_id}/profile/refresh
```

**响应**
```json
{
  "data": {
    "id": "profile_001",
    "user_id": "test_user_001",
    "profile_data": {
      "status": "available",
      "message_count": 15,
      "total_words": 1280,
      "traits": "..."
    },
    "created_at": "2024-01-20T10:50:00",
    "updated_at": "2024-01-20T11:00:00"
  }
}
```

---

## 使用流程

### 典型使用场景

```javascript
// 1. 创建对话（倾听模式）
const conv = await createConversation(userId, "listen");

// 2. 进行几轮倾听模式对话
await sendMessage(conv.id, "我最近很焦虑...");
await sendMessage(conv.id, "我害怕做不好...");
await sendMessage(conv.id, "但拖延让我更焦虑了...");

// 3. 切换到镜像模式
await switchMode(conv.id, "mirror");

// 4. 和"另一个自己"对话
await sendMessage(conv.id, "我该怎么办？");
await sendMessage(conv.id, "从哪里开始？");

// 5. 查看人格画像
const profile = await getProfile(userId);
```

---

## 两种模式对比

### 倾听模式（Listen Mode）
- **角色定位**：温暖的陪伴者
- **对话视角**：第三人称
- **回复特点**：共情、理解、适当提问
- **适用场景**：倾诉心事、情绪梳理

**示例**
```
用户: 我最近总是拖延...
灵笺: 我能感受到你此刻的纠结和疲惫。明明心里清楚该做什么，
      身体却仿佛被无形的重量压着，这种感受一定让你很困扰吧。
```

### 镜像模式（Mirror Mode）
- **角色定位**：用户的数字镜像
- **对话视角**：第一人称
- **回复特点**：自我剖析、内在声音
- **适用场景**：自我对话、决策辅助

**示例**
```
用户: 我该怎么办？
灵笺: 说实话，我知道我在逃避什么——是害怕做不好。
      但我也知道，拖延只会让焦虑更重。
      或许我该先做最小的那一步，而不是想着一次做完。
```

---

## 错误处理

所有API在失败时返回：
```json
{
  "error": "错误描述信息"
}
```

常见HTTP状态码：
- `200` - 成功
- `201` - 创建成功
- `400` - 请求参数错误
- `404` - 资源未找到
- `500` - 服务器内部错误

---

## 环境配置

需要在 `.env` 文件中配置：

```env
# 后端配置
PORT=3000
DATA_DIR=data

# AI 配置（必需）
AI_API_KEY=your_api_key
AI_API_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
```

---

## 测试

运行测试脚本：
```bash
cd Echo-Backtend
python tests/test_echo_api.py
```

---

## 前端示例

打开 `echo_demo.html` 即可体验完整功能：
- 倾听/镜像模式切换
- 实时对话
- 人格画像展示

---

## 技术栈

**后端**
- Flask 3.0
- Python 3.8+
- JSON文件存储

**AI服务**
- 支持OpenAI兼容API
- 推荐：DeepSeek V4

**前端**
- 原生HTML/CSS/JavaScript
- 无框架依赖

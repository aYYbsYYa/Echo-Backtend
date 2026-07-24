# Soul Echo 多轮实时对话与历史回响设计

## 背景

当前 `POST /api/agent/dialogue` 会依次生成 Agent A 的一次表达、Agent B 的一次回应和最终 Echo，并将完整结果写入 `data/agent_dialogues.json`。前端只有在整个请求结束后才能显示两条消息，因此对话轮次不足，也无法体现双方 Agent 正在轮流交流。

前端目前还提供一个“保存回响”按钮，但它只把最后一次 Echo 摘要写入浏览器 LocalStorage 的 `echo.soul.saved`，没有历史列表，也不能查看完整对话。后端虽然已经保存对话，却没有查询接口，导致用户无法从页面找到这些记录。

## 目标

- 每次 Agent-to-Agent 碰撞固定进行 3 轮，共 6 条发言。
- 双方 Agent 严格轮流生成，前端在每条生成完成后立即追加显示。
- 完整对话和最终 Echo 自动保存到后端，不再要求用户手动保存。
- 在 `/soul` 页面提供清晰可见的“历史回响”区域。
- 历史列表默认显示摘要，点击后展开完整 6 条对话。
- 保留现有同步接口，避免破坏已有调用方。

## 非目标

- 不实现任意轮数配置、用户自定义系统提示词或自由聊天输入。
- 不引入 WebSocket、SSE 基础设施或数据库。
- 不把真实浏览器匿名用户的内容发送给本 Demo Agent。
- 不保存生成中断时的不完整对话。
- 不提供历史记录编辑、删除或搜索功能。

## 总体方案

新增 NDJSON 流式接口 `POST /api/agent/dialogue/stream`。后端按 A、B、A、B、A、B 的顺序调用现有 OpenAI-compatible 模型服务，每生成一条发言就输出一个 `message` 事件。6 条发言完成后生成最终 Echo，写入 `data/agent_dialogues.json`，再输出 `echo` 和 `done` 事件。

新增历史查询接口 `GET /api/agent/dialogues?user_id=yeve`。前端进入 `/soul` 页面时加载最近历史，并在新对话完成后把新记录插入列表顶部。服务端记录是历史回响的唯一可信来源，删除现有 `echo.soul.saved` LocalStorage 保存逻辑和“保存回响”按钮。

现有 `POST /api/agent/dialogue` 保留，并调整为使用同一套 3 轮对话编排逻辑后一次性返回完整结果。

## 后端设计

### 多轮编排

对话固定为 3 轮，每轮包含两条发言：

1. 第 1 轮：Agent A 首先表达，Agent B 根据 A 的表达回应。
2. 第 2 轮：Agent A 结合此前对话继续推进，Agent B 再回应。
3. 第 3 轮：Agent A 收束共同主题，Agent B 给出最后回应。

生成每条消息时，模型上下文包含：

- 当前 Agent 的主人画像摘要。
- 对方 Agent 的匿名画像摘要。
- 当前已完成的全部对话消息。
- 当前轮次及发言目标。

模型调用继续统一复用后端 `.env` 中的 `AI_API_KEY`、`AI_API_URL`、`AI_MODEL`，请求格式保持标准 OpenAI Chat Completions 兼容格式。每条输出继续通过现有长度、隐私和联系方式检查；模型不可用或输出不合规时，使用与当前轮次相符的安全兜底文本，使 Demo 可以继续完成。

### 流式接口

接口：

```http
POST /api/agent/dialogue/stream
Content-Type: application/json
```

请求体：

```json
{
  "user_id": "yeve",
  "target_user_id": "kai"
}
```

响应头：

```http
Content-Type: application/x-ndjson; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
```

每个事件占一行 JSON，并以换行符结束。事件顺序固定如下：

```json
{"type":"start","data":{"agent_a":"Yeve","agent_b":"Kai","score":84,"reason":["共同关注创造"]}}
{"type":"message","data":{"round":1,"from":"Yeve","user_id":"yeve","text":"..."}}
{"type":"message","data":{"round":1,"from":"Kai","user_id":"kai","text":"..."}}
{"type":"message","data":{"round":2,"from":"Yeve","user_id":"yeve","text":"..."}}
{"type":"message","data":{"round":2,"from":"Kai","user_id":"kai","text":"..."}}
{"type":"message","data":{"round":3,"from":"Yeve","user_id":"yeve","text":"..."}}
{"type":"message","data":{"round":3,"from":"Kai","user_id":"kai","text":"..."}}
{"type":"echo","data":{"echo":"...\n\n—— Yeve Echo"}}
{"type":"done","data":{"dialogue_id":"dialogue_xxx","created_at":"2026-07-24T09:00:00Z"}}
```

`message.data.round` 表示当前轮次，取值为 1、2、3。前端不依赖网络分块边界，而是累计文本并按换行符解析完整事件，最后保留尚未形成完整行的缓冲区。

### 同步接口兼容

现有 `POST /api/agent/dialogue` 保持请求和响应外形不变，但 `conversation` 调整为 6 条消息。同步和流式接口复用同一个多轮生成器和结果构造逻辑，避免两套轮次、提示词或持久化规则出现差异。

### 持久化

完整记录继续写入：

```text
Echo-Backtend/data/agent_dialogues.json
```

记录结构保持现有字段，并为每条消息增加 `round`：

```json
{
  "id": "dialogue_xxx",
  "user_id": "yeve",
  "target_user_id": "kai",
  "agent_a": "Yeve",
  "agent_b": "Kai",
  "score": 84,
  "reason": ["共同关注创造"],
  "conversation": [
    {"round": 1, "from": "Yeve", "user_id": "yeve", "text": "..."}
  ],
  "echo": "...",
  "created_at": "2026-07-24T09:00:00Z"
}
```

只有满足以下条件时才持久化：

- 6 条消息全部生成完成。
- 最终 Echo 已生成或已使用安全兜底。
- 结果结构构造成功。

流式连接中断、生成器抛出未处理异常或请求被取消时，不写入不完整记录。流式接口在持久化完成后才发送 `done`，因此前端收到 `done` 就代表记录已经可以从历史接口读取。

### 历史查询接口

接口：

```http
GET /api/agent/dialogues?user_id=yeve
```

返回与该 Demo 用户有关的完整对话，按 `created_at` 倒序排列，默认最多返回最近 20 条。新记录优先通过顶层 `user_id` 和 `target_user_id` 判断归属；旧记录没有这两个顶层字段时，从 `conversation[*].user_id` 判断是否与查询用户有关。

响应：

```json
{
  "data": [
    {
      "id": "dialogue_xxx",
      "user_id": "yeve",
      "target_user_id": "kai",
      "agent_a": "Yeve",
      "agent_b": "Kai",
      "score": 84,
      "reason": ["共同关注创造"],
      "conversation": [
        {"round": 1, "from": "Yeve", "user_id": "yeve", "text": "第一轮表达"},
        {"round": 1, "from": "Kai", "user_id": "kai", "text": "第一轮回应"},
        {"round": 2, "from": "Yeve", "user_id": "yeve", "text": "第二轮表达"},
        {"round": 2, "from": "Kai", "user_id": "kai", "text": "第二轮回应"},
        {"round": 3, "from": "Yeve", "user_id": "yeve", "text": "第三轮表达"},
        {"round": 3, "from": "Kai", "user_id": "kai", "text": "第三轮回应"}
      ],
      "echo": "...",
      "created_at": "2026-07-24T09:00:00Z"
    }
  ]
}
```

历史数据中可能存在旧版两条消息记录。接口照常返回，前端根据实际 `conversation.length` 展示，不伪造缺失轮次。

## 前端设计

### 实时对话状态

`/soul` 页面选择共鸣对象后立即清空当前对话并调用流式接口。状态依次为：

- `connecting`：等待 `start` 事件。
- `speaking`：收到 `start` 后，显示当前等待发言的 Agent。
- `summarizing`：6 条消息完成，等待最终 Echo。
- `complete`：收到 `done`，显示“已自动保存到历史回响”。
- `error`：连接或解析失败，保留已经显示的消息并提供“重新碰撞”操作。

每收到一条 `message` 就立即追加到当前对话列表。页面显示轮次和发言方，并在列表底部显示“Agent 名称正在回应…”。新增消息后自动滚动到最新内容，但在用户开启 `prefers-reduced-motion` 时使用无动画滚动。

请求竞态继续使用请求编号控制。用户在旧请求结束前选择另一个 Agent 时，应中止旧请求并忽略旧流的后续事件，避免不同对话混合。

### 历史回响区域

在 `/soul` 页面最终 Echo 区域之后增加独立的“历史回响”区域，并在页面顶部或对话区域提供可见的锚点入口，避免用户需要猜测保存位置。

历史列表按时间倒序展示。每条默认折叠，只显示：

- 双方 Agent 名称。
- 最终 Echo 的短摘要。
- 共鸣度。
- 生成时间。
- 展开/收起按钮。

点击后在当前列表项内展开完整对话，按原顺序显示实际消息数量、轮次、发言方和内容，并显示完整最终 Echo。一次允许展开多条记录，不强制手风琴互斥，便于比较不同回响。

页面初始化时加载历史。收到流式 `done` 后，把刚完成的完整记录插入列表顶部；若随后重新请求历史，则按 `id` 去重。

历史加载失败不阻断画像、匹配和新对话流程。该区域单独显示错误及“重新读取”按钮。没有历史时显示明确空状态。

### 删除浏览器保存逻辑

移除：

- `echo.soul.saved` LocalStorage 键。
- `saved`、`saveError` 和 `saveEcho()` 页面状态及方法。
- “保存回响”按钮。

最终 Echo 完成后改为只读状态提示“已自动保存到历史回响”。浏览器 LocalStorage 仍只负责现有匿名用户状态，不承担 Agent 对话历史持久化。

## 错误处理

- 请求参数无效、目标不存在或目标与自己相同时，在流开始前返回普通 JSON 错误和对应 HTTP 状态码。
- 流开始后的意外异常输出 `error` NDJSON 事件；前端显示中文错误并保留已生成消息。
- 前端遇到未知事件类型时忽略该行，避免后端新增事件破坏旧客户端。
- 单行 JSON 解析失败时终止本次流并提示响应格式异常，防止展示错位数据。
- 历史文件不存在时按空列表处理；损坏记录由服务端过滤或跳过，不能使整个历史接口失败。

## 测试方案

### 后端

- 验证同步接口返回 A、B 严格交替的 6 条消息和 3 个轮次。
- 验证流式接口按 `start`、6 个 `message`、`echo`、`done` 的顺序输出。
- 验证每个 `message` 的轮次、用户和发言方正确。
- 验证所有模型调用继续使用现有 OpenAI-compatible 服务封装。
- 验证完整流只持久化一次，并在 `done` 前完成写入。
- 验证生成中断不会写入不完整记录。
- 验证历史接口只返回相关用户、按时间倒序且最多 20 条。
- 验证旧版两消息记录仍可查询。

### 前端

- TypeScript 构建验证 NDJSON 事件和对话类型。
- 验证分块恰好在 JSON 行中间断开时仍能正确解析。
- 验证消息按事件到达顺序实时追加，而不是等待完整响应。
- 验证错误时保留已显示消息并允许重试。
- 验证收到 `done` 后显示自动保存状态并更新历史列表。
- 验证历史默认折叠，点击后显示完整对话，再次点击收起。
- 验证空历史、历史加载错误、旧版两消息记录和移动端布局。
- 验证 375px 手机宽度无横向溢出，长 Echo 和长 Agent 发言不会遮挡控件。

## 验收标准

- 用户选择共鸣对象后，可以看到双方 Agent 固定进行 3 轮、共 6 条轮流对话。
- 每条消息生成完成后立即显示，页面能明确指出当前发言方或总结状态。
- 对话完整结束后自动保存，页面不再出现需要手动保存的按钮。
- 用户能在 `/soul` 页面直接找到“历史回响”，默认看到摘要，点击后查看完整对话。
- 刷新页面后历史仍然存在，并从后端记录恢复。
- 不完整或中断的流不会出现在历史列表中。
- 原同步接口仍可使用，并返回相同的 6 条对话结果结构。

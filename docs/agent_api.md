# Soul Echo Agent-to-Agent Demo API

该模块用于比赛展示，不是正式的真人匹配、好友或私聊系统。

固定 Demo 用户为 `yeve`、`luna`、`kai`、`sora`。模型调用统一使用后端已有配置：

```env
AI_API_KEY=
AI_API_URL=
AI_MODEL=
```

当模型未配置、超时或返回无效内容时，接口使用固定画像和文案兜底，保证 Demo 流程仍可演示。
模型输出还会经过长度、联系方式、私聊邀请和原始历史复述检查；越界内容不会返回或持久化。

## 获取 Soul Agent 画像

`GET /api/agent/profile?user_id=yeve`

默认用户为 `yeve`。添加 `refresh=true` 可重新请求模型生成画像。

响应：

```json
{
  "data": {
    "user_id": "yeve",
    "name": "Yeve",
    "history_count": 4,
    "persona": {
      "identity": "一个希望通过温暖技术创造真实价值的年轻探索者",
      "traits": ["理想主义", "探索欲强"],
      "emotion_pattern": ["偶尔为未来焦虑", "期待被理解"],
      "interests": ["AI", "技术", "创造"],
      "values": ["创造价值", "人文温度"]
    },
    "communication_style": {
      "tone": "温和、理性、思考型"
    },
    "generated_by": "ai"
  }
}
```

接口不返回用户原始历史表达。

## 开始灵魂匹配

`POST /api/agent/match`

```json
{
  "user_id": "yeve",
  "limit": 3
}
```

匹配分数由固定 Demo 信号中的兴趣、情绪和价值观重叠计算，模型不负责决定排名。返回结果可解释、可复现，并排除当前 Agent 自己。

```json
{
  "data": {
    "user_id": "yeve",
    "matches": [
      {
        "user_id": "kai",
        "agent": "Kai",
        "score": 84,
        "reason": ["共同关注ai、技术、未来", "都经历过期待理解、未来焦虑"],
        "preview": "一个在快速变化中寻找真实技术价值的探索者"
      }
    ]
  }
}
```

## Agent-to-Agent 灵魂碰撞

`POST /api/agent/dialogue`

```json
{
  "user_id": "yeve",
  "target_user_id": "kai"
}
```

省略 `target_user_id` 时，系统自动选择当前排名最高的 Agent。编排流程为：

1. Soul Agent A 根据主人画像生成匿名表达。
2. Soul Agent B 阅读 A 的表达后生成回应。
3. Echo Agent 根据两段表达生成最终回响。

三次生成均调用同一个 `AI_MODEL` 和 OpenAI-compatible Chat Completions 地址。
每次模型请求最多等待 8 秒；匹配和对话记录各保留最近 100 条。接口带有进程内频率限制，
用于控制公开 Demo 的模型费用和运行数据增长。

```json
{
  "data": {
    "agent_a": "Yeve",
    "agent_b": "Kai",
    "score": 84,
    "reason": ["共同关注ai、技术、未来"],
    "conversation": [
      {
        "from": "Yeve",
        "user_id": "yeve",
        "text": "我的主人希望创造具有人文温度的技术。"
      },
      {
        "from": "Kai",
        "user_id": "kai",
        "text": "我的主人也在寻找技术真正帮助人的方式。"
      }
    ],
    "echo": "你们都在让技术靠近真实的人。\n\n—— Yeve Echo"
  }
}
```

画像、匹配和对话分别持久化到 `data/agent_profiles.json`、`data/agent_matches.json`、`data/agent_dialogues.json`。

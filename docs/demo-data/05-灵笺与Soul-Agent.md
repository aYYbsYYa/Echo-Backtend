# 灵笺与 Soul Agent 演示数据

## 1. 灵笺会话

```json
{
  "id": "demo_echo_conversation_main",
  "user_id": "demo_user_main",
  "mode": "listen",
  "created_at": "now - 6 天",
  "updated_at": "now - 1 天"
}
```

## 2. 五轮对话

消息 ID 从 `demo_echo_message_01` 到 `demo_echo_message_10`，全部关联 `demo_echo_conversation_main`。时间按表中顺序递增，角色分别使用 `user` 和 `assistant`。

| 序号 | role | mode | 内容 |
|---:|---|---|---|
| 1 | user | listen | 最近所有人都在问我毕业以后去哪里，我每次都装作已经想好了，其实我很害怕自己选错。 |
| 2 | assistant | listen | 你好像不只是担心一个选择，也在承受“应该已经有答案”的压力。每次这样回答别人之后，你心里最明显的感受是什么？ |
| 3 | user | listen | 有点累，也会觉得自己让家里失望。他们没有逼我，但越是这样，我越觉得应该交出一个漂亮的结果。 |
| 4 | assistant | listen | 没有人直接催促你，可你把他们的期待放在了自己肩上。那份“必须交出漂亮结果”的声音，似乎已经盖过了你真正想要什么。 |
| 5 | user | mirror | 是。我其实想先做一个自己相信的项目，哪怕它暂时不能证明什么。但我又怕这只是逃避找工作。 |
| 6 | assistant | mirror | 你一边珍惜创造真实价值的愿望，一边又用“逃避”审视它。或许需要区分的不是稳定与冒险，而是：这个选择让你更接近自己，还是只是让你躲开恐惧。 |
| 7 | user | mirror | 如果诚实一点，我并不讨厌走得慢。我害怕的是别人已经走远，而我还解释不清自己在做什么。 |
| 8 | assistant | mirror | 你在意的可能不是速度，而是自己的路暂时没有被外界看懂。即使如此，你仍然愿意为真实和长期意义留下位置。 |
| 9 | user | listen | 这样说以后，好像没有那么急着马上证明自己了。我还是会焦虑，但至少知道焦虑不等于方向错了。 |
| 10 | assistant | listen | 你没有消除不确定，却开始把它和失败区分开。这或许就是一种方向感：不是提前知道终点，而是在选择中仍能认出自己重视的东西。 |

时间建议：第一轮为 `now - 6 天`，后续每条递增 3～20 分钟；最后两条为 `now - 1 天`。

## 3. 人格画像

`echo_profiles.json` 每条记录外层保留 `id`、`user_id`、`profile_data`、`created_at`、`updated_at`；其中外层 `profile_data` 的值必须完整等于 `generate_profile_summary()` 的返回值，即 `{status, message_count, profile_data: {persona, communication_style}}`。不得再增加第三层 `profile_data`。

```json
{
  "id": "demo_echo_profile_main",
  "user_id": "demo_user_main",
  "profile_data": {
    "status": "available",
    "message_count": 5,
    "profile_data": {
      "persona": {
        "identity": "一个在未来选择中寻找真实方向的年轻探索者",
        "traits": ["善于自省", "表达克制", "重视长期意义"],
        "emotion_pattern": ["面对外界期待时容易自我施压", "在不确定中反复确认选择是否真实"],
        "interests": ["温暖技术", "创造", "自我成长"],
        "values": ["真实体验", "创造价值", "按自己的速度成长"]
      },
      "communication_style": {
        "tone": "沉静、真诚、带有反思感"
      }
    }
  },
  "created_at": "now - 1 天",
  "updated_at": "now - 1 天"
}
```

`message_count` 统计用户消息数，因此五轮对话应为 5，而不是消息总数 10。

## 4. Soul Agent 角色

现有 `app/agent/demo_data/users.json` 已提供 Yeve、Luna、Kai、Sora 四个固定人物。初始化时建议复用其 `seed_profile` 生成 `agent_profiles.json`，不要维护第二套相互冲突的人物文案。

主推匹配结果：

```json
{
  "id": "demo_agent_match_yeve",
  "user_id": "yeve",
  "matches": [
    {
      "user_id": "kai",
      "agent": "Kai",
      "score": 84,
      "reason": [
        "共同关注 AI、技术与未来",
        "都经历过成长速度和未来方向的焦虑",
        "都重视创造真实价值与持续成长"
      ],
      "preview": "一个在快速变化中寻找真实技术价值的探索者"
    },
    {
      "user_id": "luna",
      "agent": "Luna",
      "score": 66,
      "reason": ["共同关注创造与真实表达", "都期待技术或作品保有人文温度"],
      "preview": "一个通过音乐保护真实表达的创作者"
    },
    {
      "user_id": "sora",
      "agent": "Sora",
      "score": 55,
      "reason": ["都在不确定中寻找方向", "都重视真实生活和持续成长"],
      "preview": "一个通过生活和远方寻找自身方向的大学生"
    }
  ],
  "created_at": "now - 30 分钟"
}
```

## 5. Yeve 与 Kai 的代理对话

建议预置 6 轮代理碰撞，用于 AI 不可用时仍能演示：

1. Yeve Agent：我的用户一直在想，技术是否能理解那些没有说出口的情绪。
2. Kai Agent：我的用户更常问，技术怎样解决真实问题，而不是只显得先进。两者也许指向同一个标准。
3. Yeve Agent：是的，温暖不应该只是界面风格，而应该体现在产品是否减少表达压力。
4. Kai Agent：那就意味着系统需要克制。不是建立更多关系，而是在合适的时候允许连接结束。
5. Yeve Agent：这也是我的用户在寻找的答案：技术可以陪伴，但不必占有人的注意力。
6. Kai Agent：我们共同的回声或许是，真正以人为本的技术，也知道什么时候安静下来。

固定回声：

> 真正以人为本的技术，不只知道如何连接，也知道什么时候安静下来。

## 6. 演示限制

- 灵笺 v2 前端当前未注册正式路由，可先通过后端 `echo_demo.html` 展示。
- Soul Agent 前端未稳定前，将其作为加分项，不放在主演示链路。
- Seed 画像保证无 AI Key 时也有结果；现场生成仅作为增强，不应成为成功演示的前置条件。

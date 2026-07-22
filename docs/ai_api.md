# AI API

## 审核文本

`POST /api/ai/moderate`

```json
{"content":"我想把今天的晚风装进一句话里。"}
```

成功返回 `200`：

```json
{
  "data": {"safe": true, "reason": "正常文字"},
  "provider": "local-fallback"
}
```

Demo 默认执行本地关键词审核，拒绝色情、暴力、极端政治、广告、骚扰和违法相关内容。`AI_API_KEY`、`AI_API_URL` 与 `AI_MODEL` 已作为未来模型接入配置保留；接入时必须维持上述 JSON 响应契约。

# 用户 API

## 创建匿名身份

`POST /api/users`

请求：

```json
{
  "id": "usr_8d2e...",
  "nickname": "小明",
  "birthday": "2001-06-01",
  "gender": "prefer_not_to_say",
  "region": "杭州"
}
```

`id` 由浏览器以用户资料、时间戳与随机 salt 混合生成。相同 ID 重复提交将返回原资料，不会覆盖已创建身份。

成功返回 `201`：

```json
{
  "data": {"id": "usr_8d2e...", "nickname": "小明", "avatar": "小", "region": "杭州"}
}
```

## 查询身份

`GET /api/users/:userId`

成功返回 `200`，未知身份返回 `404`。

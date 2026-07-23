# 纸飞机 API

## 发布

`POST /api/planes`

```json
{"user_id":"usr_8d2e...","content":"今天也想把一句谢谢送给陌生人。"}
```

成功返回 `201`。服务会随机分配 `sky`、`window` 或 `tree` 场景，调用 AI 模型生成开发组回信，并由前端以对应动画表现纸飞机去向。AI 未配置或调用失败时，纸飞机仍会发布，`reply` 为 `null`。

## 接住

`GET /api/planes/discover?user_id=usr_8d2e...`

随机返回一架非本人发布的纸飞机并递增浏览量。没有候选时返回 `{ "data": null }`。

## 我的纸飞机

`GET /api/planes/mine/:userId`

按发布时间倒序返回本人发布的纸飞机、浏览量和场景。

## 详情

`GET /api/planes/:planeId?user_id=usr_8d2e...`

返回纸飞机正文、匿名作者、地区、落点场景、投出时间和停留次数；作者查看自己的纸飞机时额外返回 `is_author: true` 和 `reply`。

# 纸飞机 API

## 发布

`POST /api/planes`

```json
{"user_id":"usr_8d2e...","content":"今天也想把一句谢谢送给陌生人。"}
```

成功返回 `201`。服务会随机分配 `sky`、`window` 或 `tree` 场景，前端以对应动画表现纸飞机去向。

## 接住

`GET /api/planes/discover?user_id=usr_8d2e...`

随机返回一架非本人发布的纸飞机并递增浏览量。没有候选时返回 `{ "data": null }`。

## 我的纸飞机

`GET /api/planes/mine/:userId`

按发布时间倒序返回本人发布的纸飞机、浏览量和场景。

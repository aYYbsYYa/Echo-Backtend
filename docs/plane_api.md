# 纸飞机 API

## 发布

`POST /api/planes`

纯文字发布可继续使用 JSON：

```json
{"user_id":"usr_8d2e...","content":"今天也想把一句谢谢送给陌生人。"}
```

图文发布使用 `multipart/form-data`，字段为 `user_id`、`content` 和可选文件 `image`。图片支持 JPEG、PNG、WebP、GIF，默认最大 5MB，成功响应通过 `image_url` 返回访问地址。服务会随机分配 `sky`、`window` 或 `tree` 场景，并尝试调用 AI 模型生成开发组回信。

## 接住

`GET /api/planes/discover?user_id=usr_8d2e...`

随机返回一架非本人发布的纸飞机并递增浏览量。没有候选时返回 `{ "data": null }`。

## 我的纸飞机

`GET /api/planes/mine/:userId`

按发布时间倒序返回本人发布的纸飞机、浏览量和场景。

## 详情

`GET /api/planes/:planeId?user_id=usr_8d2e...`

返回纸飞机正文、匿名作者、地区、落点场景、投出时间和停留次数；作者查看自己的纸飞机时额外返回 `is_author: true` 和 `reply`。

接收者可以像漂流瓶一样留下心意或留言：

`POST /api/planes/:planeId/likes`

```json
{"user_id":"usr_8d2e..."}
```

`POST /api/planes/:planeId/comments`

```json
{"user_id":"usr_8d2e...","content":"愿这句话顺利抵达。"}
```

点赞数量和留言仅作者查看自己的纸飞机时返回；留言包含评论者昵称和 UTC 时间戳，前端展示为“来自 xxx · x 分钟前”。接收者不会看到开发组回信或作者私有统计。

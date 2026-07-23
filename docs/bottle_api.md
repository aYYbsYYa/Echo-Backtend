# 漂流瓶 API

## 发布

`POST /api/bottles`

```json
{"user_id":"usr_8d2e...","content":"希望今晚的风能轻一点。"}
```

内容长度为 1 到 500 字符。内容通过基础字段校验后写入漂流瓶，并尝试调用配置的 AI 模型生成开发组回信。AI 未配置或调用失败时，漂流瓶仍会正常发布，`reply` 为 `null`。

## 捞取

`GET /api/bottles/discover?user_id=usr_8d2e...`

接口从其他用户发布的公开漂流瓶中完全随机返回一条内容，不再接收随机/Echo 模式参数，也不使用算法推荐。没有候选时 `data` 为 `null`。

## 详情

`GET /api/bottles/:bottleId?user_id=usr_8d2e...`

接收者可获得内容、昵称、地区与漂流时间。作者额外获得浏览数、点赞数、评论和开发组回信。

## 点赞与留言

`POST /api/bottles/:bottleId/likes`

```json
{"user_id":"usr_8d2e..."}
```

重复调用会切换点赞状态。

`POST /api/bottles/:bottleId/comments`

```json
{"user_id":"usr_8d2e...","content":"愿你被温柔接住。"}
```

留言仅发布者通过自己的历史接口查看；每条留言包含评论者昵称和 UTC 时间戳，前端显示为“来自 xxx · x 分钟前”。

## 我的漂流瓶

`GET /api/bottles/mine/:userId`

按发布时间倒序返回作者私有统计与留言。

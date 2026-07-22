# 漂流瓶 API

## 发布

`POST /api/bottles`

```json
{"user_id":"usr_8d2e...","content":"希望今晚的风能轻一点。"}
```

内容长度为 1 到 500 字符。服务先审核，审核通过后写入漂流瓶并生成官方回信。成功返回 `201`；审核拒绝返回 `422`。

## 捞取

`GET /api/bottles/discover?user_id=usr_8d2e...&mode=random`

`mode` 可为 `random` 或 `echo`。Echo 模式根据作者已发布文本标签的重叠度排序，并加入随机探索因子。成功返回单个公开瓶子；没有候选时 `data` 为 `null`。

## 详情

`GET /api/bottles/:bottleId?user_id=usr_8d2e...`

接收者只获得内容、昵称、地区与漂流时间。作者额外获得浏览数、点赞数、留言和官方回信。

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

留言仅发布者通过自己的历史接口看到。

## 我的漂流瓶

`GET /api/bottles/mine/:userId`

按发布时间倒序返回作者私有统计与留言。

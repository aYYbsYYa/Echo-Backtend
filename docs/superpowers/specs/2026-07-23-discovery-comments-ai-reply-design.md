# Discovery, Comments, and AI Reply Design

## Scope

This change fixes and clarifies four behaviors:

1. Discovery keeps excluding the current user's own content and shows an explicit empty state when no other content exists.
2. The AI publishing moderation module is removed.
3. Bottle publishing generates the development-team reply through an OpenAI-compatible Chat Completions request instead of a fixed template.
4. Bottle comments expose the commenter's nickname and relative age to the author, while discovered bottles show how long they have been drifting.

Paper planes remain without official AI replies or comments.

## Architecture

### AI reply service

Add `app/services/ai_service.py` as the only module that knows the OpenAI-compatible HTTP contract. It will:

- read `AI_API_KEY`, `AI_API_URL`, and `AI_MODEL` from `Config`;
- normalize `AI_API_URL` so both a full `/chat/completions` endpoint and a base URL ending in `/v1` are supported;
- send `Authorization: Bearer <key>` and JSON content headers;
- send a standard Chat Completions body with `model` and `messages`;
- parse `choices[0].message.content` into a trimmed reply;
- return `None` for missing configuration, transport failures, invalid JSON, non-success status codes, or an empty/malformed model response.

The system prompt will require a concise, empathetic reply grounded in the author's nickname, region, and published content, ending with `Yeve（伊芙梦）开发组`. It must not claim professional, medical, legal, or emergency intervention.

Bottle publishing remains synchronous for this demo. AI failure must not block publication and must not fall back to a fixed reply.

### Removal of publishing moderation

Remove the `/api/ai/moderate` blueprint and its application registration. Bottle publishing will stop calling `moderate_locally`; both bottle and plane publishing will use the same validation boundary: valid user identity and content length from 1 to 500 characters.

Remove obsolete moderation documentation and README references. Tag extraction remains because Echo recommendation still depends on it.

### Comment representation

New comments will persist:

```json
{
  "id": "comment_...",
  "item_id": "bottle_...",
  "user_id": "usr_...",
  "nickname": "匿名昵称",
  "content": "评论内容",
  "created_at": "2026-07-23T02:00:00+00:00"
}
```

Only the bottle author receives comments through the existing private bottle response. For older records without `nickname`, `public_bottle` will look up the user by `user_id` and return a fallback nickname without rewriting historical JSON.

The frontend `EchoComment` type will add `nickname` and retain `created_at`. The author view will render each comment as:

```text
来自 昵称 · 5 分钟前
评论内容
```

Relative time is calculated when the view renders: just now, minutes, hours, or days ago.

### Drift duration and discovery empty state

`DiscoveryCard` will replace the absolute date with elapsed drift time:

- less than 24 hours: `已漂流了不到 1 天`;
- otherwise: `已漂流了 N 天`, using completed 24-hour periods.

Discovery API behavior does not change: candidates authored by the current user remain excluded and an empty candidate set returns `data: null`. The frontend API client will preserve the response `message` for discovery calls so `HomeView` can distinguish bottle and plane empty states instead of presenting a generic missing-content message.

## Data Flow

### Bottle publishing

1. Validate content and user identity.
2. Generate tags and create the bottle record.
3. Call the AI reply service with nickname, region, and content.
4. Store the returned reply or `null`.
5. Persist the bottle and return the existing public response envelope.

### Comment creation and author display

1. Validate bottle, commenter identity, and content.
2. Persist the comment with commenter nickname and UTC timestamp.
3. When the author loads the bottle, return normalized private comments.
4. The frontend calculates relative time from each comment timestamp at display time.

### Discovery

1. Filter out content authored by the current user.
2. Return a selected item or `data: null` with a kind-specific message.
3. The frontend renders content with drift duration or the returned empty-state message.

## Error Handling

- Invalid publishing or commenting input keeps the existing `400` response style.
- AI configuration or provider failures are treated as reply-generation failures, not publishing failures.
- AI responses are accepted only when `choices[0].message.content` is a non-empty string.
- Existing comments with missing or deleted users use `匿名旅人` as the nickname.
- Invalid timestamps degrade to a neutral display rather than breaking the page.

## Verification

Backend tests will cover:

- bottle and plane discovery returning kind-specific empty messages while excluding self-authored items;
- publishing no longer invoking moderation;
- OpenAI-compatible request headers, endpoint, payload, response parsing, and failure behavior;
- comment persistence with nickname and timestamp;
- normalization of legacy comments without nickname.

Frontend verification will cover:

- TypeScript build and type checking;
- discovery envelope handling and empty-state messages;
- comment source and relative-time rendering;
- drift-duration wording for under one day and multiple days.

## Compatibility

Existing JSON bottle and comment data remains readable. No migration is required. The removed moderation endpoint is an intentional breaking API removal requested for this demo.

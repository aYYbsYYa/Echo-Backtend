from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


USERS = (
    ("demo_user_main", "林间旅人", "2000-01-01", "prefer_not_to_say", "杭州", "林"),
    ("demo_user_wind", "晚风来信", "1999-08-17", "prefer_not_to_say", "南京", "晚"),
    ("demo_user_tide", "潮汐以北", "1998-03-12", "female", "青岛", "潮"),
    ("demo_user_moon", "月台尽头", "2001-11-06", "male", "武汉", "月"),
    ("demo_user_pine", "松针落下", "1999-05-21", "prefer_not_to_say", "成都", "松"),
    ("demo_user_cloud", "云层背面", "2002-02-09", "female", "厦门", "云"),
    ("demo_user_lamp", "留一盏灯", "1997-09-30", "male", "上海", "留"),
    ("demo_user_whale", "听鲸的人", "2000-06-18", "prefer_not_to_say", "大连", "听"),
    ("demo_user_rain", "雨停之前", "2001-04-03", "female", "长沙", "雨"),
    ("demo_user_star", "迟到的星光", "1998-12-24", "male", "西安", "迟"),
)

BOTTLES = (
    ("demo_user_main", "deep", 3 * 86400, 34, "毕业之后，大家都在问我找到了什么工作，好像人生突然只剩下一张 offer 可以证明自己。其实我更想知道，如果暂时走得慢一点，是不是也没有关系。"),
    ("demo_user_main", "drift", 9 * 86400, 21, "昨晚整理宿舍，翻到刚入学时写下的愿望。四年过去，我没有成为当时想象中很厉害的人，但好像更知道自己不愿意成为什么样的人了。"),
    ("demo_user_tide", "deep", 7 * 3600, 46, "来到新的城市工作以后，我习惯每周给家里打一次电话。总是说吃得很好、同事很好，却没有说有时下班走出地铁，会突然很想念家门口那条普通的小路。"),
    ("demo_user_moon", "drift", 86400, 18, "送朋友去车站时，我们都没有说以后会不会渐渐失去联系。列车开走之后我才意识到，有些告别不是关系结束，只是大家开始走向不同的生活。"),
    ("demo_user_pine", "shallow", 4 * 86400, 29, "做了很久的作品没有得到想象中的回应。我知道不应该只用掌声判断它的价值，可安静下来的时候，还是会怀疑那些投入到底有没有意义。"),
    ("demo_user_lamp", "deep", 35 * 60, 11, "最近工作总是出错，我开始害怕打开新的消息。今天还是把最难的那件事做完了，没有变得轻松很多，但至少没有继续逃开。"),
    ("demo_user_whale", "drift", 2 * 86400, 37, "凌晨三点又醒了。城市安静得像只剩下冰箱的声音。我没有特别难过，只是希望这个世界上也有人在这样的夜里，允许自己暂时不坚强。"),
    ("demo_user_rain", "shallow", 6 * 86400, 25, "今天第一次明确拒绝了一件让我长期不舒服的事。说出口时手一直在抖，后来才发现，保护自己并不等于伤害别人。"),
    ("demo_user_star", "drift", 12 * 86400, 42, "我想象过很多次未来的家。它不需要很大，但窗边要有一张桌子，能够放下书、晚饭和一些还没完成的计划。希望那时的我依然愿意期待明天。"),
    ("demo_user_wind", "shallow", 10 * 3600, 16, "今天收到了一位陌生人的帮助，对方甚至没有留下名字。原来有些善意不需要被记住，也能让普通的一天改变一点方向。"),
)

PLANES = (
    ("demo_user_main", "window", 2 * 3600, 19, "今天下课时看见一片很慢的云。突然觉得，暂时没有答案也不妨碍继续生活。"),
    ("demo_user_main", "tree", 5 * 86400, 27, "把用了四年的宿舍钥匙交回去了。门关上的声音很轻，青春好像也是。"),
    ("demo_user_cloud", "sky", 18 * 60, 8, "下班时遇到很好看的晚霞，分给一个此刻需要的人。"),
    ("demo_user_wind", "window", 4 * 3600, 15, "希望正在等结果的你，今晚先睡一个好觉。"),
    ("demo_user_rain", "tree", 86400, 23, "第一次一个人去看电影，好像也没有想象中孤单。"),
    ("demo_user_star", "sky", 3 * 86400, 31, "今天鼓起勇气投出了那份一直不敢投的申请。结果交给明天。"),
    ("demo_user_lamp", "window", 7 * 3600, 13, "如果今天很累，就允许自己只完成今天。"),
    ("demo_user_moon", "tree", 8 * 86400, 24, "火车经过一片亮着灯的房子。祝那里的人，也祝路上的人。"),
    ("demo_user_pine", "sky", 2 * 86400, 17, "删掉又重写很多次，最后还是决定把作品发出去。"),
    ("demo_user_whale", "window", 6 * 86400, 22, "夜里听到一首旧歌，想起一个已经不再联系的人。没有遗憾，只是想起。"),
)

REPLIES = {
    "demo_bottle_01": "林间旅人，谢谢你把这份犹疑放进海里。这里不会催你抵达，愿你先按自己的速度，走过眼前这一小段路。",
    "demo_bottle_02": "愿望不只负责检验我们有没有做到，也会照见我们如何改变。谢谢你认真看见了这四年的自己。",
    "demo_plane_01": "有些答案适合追赶，有些答案需要等它慢慢靠近。愿今天的云替你保管一会儿焦虑。",
    "demo_plane_02": "钥匙交还了，走过的时间仍然属于你。愿你带着那些具体的日子，走进新的生活。",
}

PRIMARY_COMMENTS = (
    ("demo_comment_bottle_01_01", "demo_bottle_01", "demo_user_wind", 2 * 86400, "慢一点也没有关系。你不是一张 offer，也不需要用一个结果解释完整的自己。"),
    ("demo_comment_bottle_01_02", "demo_bottle_01", "demo_user_tide", 86400, "我也经过这段路。后来发现，方向常常是在走动以后才慢慢出现的。"),
    ("demo_comment_bottle_01_03", "demo_bottle_01", "demo_user_rain", 8 * 3600, "认真读完了。希望你在回答别人之前，也先听见自己的答案。"),
    ("demo_comment_bottle_02_01", "demo_bottle_02", "demo_user_moon", 7 * 86400, "知道自己不愿成为什么，也是一种很重要的抵达。"),
    ("demo_comment_bottle_02_02", "demo_bottle_02", "demo_user_cloud", 5 * 86400, "四年前的你如果看到现在，或许也会为你保留真实而高兴。"),
    ("demo_comment_plane_01_01", "demo_plane_01", "demo_user_wind", 90 * 60, "接住这句话了。今天也允许自己先生活，再寻找答案。"),
    ("demo_comment_plane_01_02", "demo_plane_01", "demo_user_cloud", 45 * 60, "我窗外也有一片很慢的云。谢谢你把它写下来。"),
    ("demo_comment_plane_02_01", "demo_plane_02", "demo_user_moon", 4 * 86400, "有些重要的告别确实很轻。祝下一扇门后也有光。"),
)

INTERACTION_COUNTS = {
    "demo_bottle_03": (5, 2), "demo_bottle_04": (3, 1),
    "demo_bottle_05": (4, 2), "demo_bottle_06": (2, 1),
    "demo_bottle_07": (5, 2), "demo_bottle_08": (4, 1),
    "demo_bottle_09": (6, 2), "demo_bottle_10": (3, 1),
    "demo_plane_03": (3, 1), "demo_plane_04": (4, 1),
    "demo_plane_05": (2, 1), "demo_plane_06": (5, 1),
    "demo_plane_07": (3, 1), "demo_plane_08": (4, 1),
    "demo_plane_09": (3, 1), "demo_plane_10": (2, 1),
}

COMMENT_TEXTS = (
    "谢谢你写下这些，我今天刚好需要看到。",
    "不知道该说什么，但我认真读完了。",
    "路过这里，想把一点安静留给你。",
    "我也经历过相似的时刻，希望你不用急着找到答案。",
    "愿这件小事在你明天醒来时，仍然有一点光。",
    "接住了。也把一句祝福放回风里。",
)

ECHO_MESSAGES = (
    ("user", "listen", "最近所有人都在问我毕业以后去哪里，我每次都装作已经想好了，其实我很害怕自己选错。"),
    ("assistant", "listen", "你好像不只是担心一个选择，也在承受“应该已经有答案”的压力。每次这样回答别人之后，你心里最明显的感受是什么？"),
    ("user", "listen", "有点累，也会觉得自己让家里失望。他们没有逼我，但越是这样，我越觉得应该交出一个漂亮的结果。"),
    ("assistant", "listen", "没有人直接催促你，可你把他们的期待放在了自己肩上。那份“必须交出漂亮结果”的声音，似乎已经盖过了你真正想要什么。"),
    ("user", "mirror", "是。我其实想先做一个自己相信的项目，哪怕它暂时不能证明什么。但我又怕这只是逃避找工作。"),
    ("assistant", "mirror", "你一边珍惜创造真实价值的愿望，一边又用“逃避”审视它。或许需要区分的不是稳定与冒险，而是：这个选择让你更接近自己，还是只是让你躲开恐惧。"),
    ("user", "mirror", "如果诚实一点，我并不讨厌走得慢。我害怕的是别人已经走远，而我还解释不清自己在做什么。"),
    ("assistant", "mirror", "你在意的可能不是速度，而是自己的路暂时没有被外界看懂。即使如此，你仍然愿意为真实和长期意义留下位置。"),
    ("user", "listen", "这样说以后，好像没有那么急着马上证明自己了。我还是会焦虑，但至少知道焦虑不等于方向错了。"),
    ("assistant", "listen", "你没有消除不确定，却开始把它和失败区分开。这或许就是一种方向感：不是提前知道终点，而是在选择中仍能认出自己重视的东西。"),
)

AGENT_DIALOGUE = (
    (1, "Yeve", "yeve", "我的用户一直在想，技术是否能理解那些没有说出口的情绪。"),
    (1, "Kai", "kai", "我的用户更常问，技术怎样解决真实问题，而不是只显得先进。两者也许指向同一个标准。"),
    (2, "Yeve", "yeve", "是的，温暖不应该只是界面风格，而应该体现在产品是否减少表达压力。"),
    (2, "Kai", "kai", "那就意味着系统需要克制。不是建立更多关系，而是在合适的时候允许连接结束。"),
    (3, "Yeve", "yeve", "这也是我的用户在寻找的答案：技术可以陪伴，但不必占有人的注意力。"),
    (3, "Kai", "kai", "我们共同的回声或许是，真正以人为本的技术，也知道什么时候安静下来。"),
)


def _load_agent_users() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / "agent" / "demo_data" / "users.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_demo_data(now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("演示数据基准时间必须包含时区。")
    now = now.astimezone(timezone.utc)
    iso = lambda delta: (now + delta).isoformat()

    users = [dict(zip(("id", "nickname", "birthday", "gender", "region", "avatar"), row)) for row in USERS]
    user_map = {item["id"]: item for item in users}

    bottles = []
    planes = []
    for prefix, source, target in (("bottle", BOTTLES, bottles), ("plane", PLANES, planes)):
        for index, (user_id, scene, age, views, content) in enumerate(source, 1):
            item_id = f"demo_{prefix}_{index:02d}"
            target.append({
                "id": item_id, "content": content,
                "image": "demo_rainy_walk.jpeg" if item_id == "demo_bottle_10" else ("demo_sunset.png" if item_id == "demo_plane_03" else None),
                "user_id": user_id, "region": user_map[user_id]["region"],
                "created_at": iso(timedelta(seconds=-age)), "scene": scene,
                "views": views, "reply": REPLIES.get(item_id),
            })

    author_by_item = {item["id"]: item["user_id"] for item in bottles + planes}
    all_user_ids = [item[0] for item in USERS]
    likes = []
    comments = []
    primary_likes = {
        "demo_bottle_01": ["demo_user_wind", "demo_user_tide", "demo_user_pine", "demo_user_lamp", "demo_user_whale", "demo_user_rain"],
        "demo_bottle_02": ["demo_user_wind", "demo_user_moon", "demo_user_cloud", "demo_user_star"],
        "demo_plane_01": ["demo_user_wind", "demo_user_cloud", "demo_user_lamp", "demo_user_star", "demo_user_tide"],
        "demo_plane_02": ["demo_user_wind", "demo_user_moon", "demo_user_pine"],
    }
    like_index = 1
    for item_id, user_ids in primary_likes.items():
        for user_id in user_ids:
            likes.append({"id": f"demo_like_{like_index:03d}", "item_id": item_id, "user_id": user_id})
            like_index += 1
    for item_id, (like_count, comment_count) in INTERACTION_COUNTS.items():
        candidates = [user_id for user_id in all_user_ids if user_id != author_by_item[item_id]]
        offset = sum(ord(char) for char in item_id) % len(candidates)
        selected = (candidates[offset:] + candidates[:offset])[:like_count]
        for user_id in selected:
            likes.append({"id": f"demo_like_{like_index:03d}", "item_id": item_id, "user_id": user_id})
            like_index += 1
        for comment_number, user_id in enumerate(selected[:comment_count], 1):
            comments.append({
                "id": f"demo_comment_{item_id.removeprefix('demo_')}_{comment_number:02d}",
                "item_id": item_id, "user_id": user_id,
                "nickname": user_map[user_id]["nickname"],
                "content": COMMENT_TEXTS[(like_index + comment_number) % len(COMMENT_TEXTS)],
                "created_at": iso(timedelta(hours=-(comment_number + 2))),
            })
    for comment_id, item_id, user_id, age, content in PRIMARY_COMMENTS:
        comments.append({
            "id": comment_id, "item_id": item_id, "user_id": user_id,
            "nickname": user_map[user_id]["nickname"], "content": content,
            "created_at": iso(timedelta(seconds=-age)),
        })

    capsules = [
        {"id": "demo_capsule_opened", "content": "我很害怕毕业，觉得没有明确方向就是失败。现在虽然还是没有完全想清楚，但至少已经知道，方向不是一次决定出来的。", "user_id": "demo_user_main", "mood": "lost", "duration": "month12", "custom_seconds": None, "has_image": False, "created_at": iso(timedelta(days=-365)), "unlock_at": iso(timedelta(days=-2)), "opened_at": iso(timedelta(days=-1))},
        {"id": "demo_capsule_unlockable", "content": "如果你打开了这封信，希望你还记得离开学校那天的晚霞。那时你不知道会去哪里，但还是认真地和过去告别了。", "user_id": "demo_user_main", "mood": "miss", "duration": "month1", "custom_seconds": None, "has_image": False, "created_at": iso(timedelta(days=-30)), "unlock_at": iso(timedelta(minutes=-5)), "opened_at": None},
        {"id": "demo_capsule_locked", "content": "写给一年后的我：希望你没有因为走得慢，就否定这一年的努力。也希望你仍然愿意做一些温暖、真实、暂时看不到回报的事情。", "user_id": "demo_user_main", "mood": "expect", "duration": "month12", "custom_seconds": None, "has_image": False, "created_at": iso(timedelta(days=-2)), "unlock_at": iso(timedelta(days=363)), "opened_at": None},
        {"id": "demo_capsule_soon", "content": "60秒之后，愿这朵向日葵告诉你：所有朝着光的等待，都不会被辜负。", "user_id": "demo_user_main", "mood": "calm", "duration": "custom", "custom_seconds": 60, "has_image": True, "created_at": iso(timedelta(seconds=-50)), "unlock_at": iso(timedelta(seconds=10)), "opened_at": None},
    ]

    echo_conversations = [{"id": "demo_echo_conversation_main", "user_id": "demo_user_main", "mode": "listen", "created_at": iso(timedelta(days=-6)), "updated_at": iso(timedelta(days=-1))}]
    echo_messages = []
    for index, (role, mode, content) in enumerate(ECHO_MESSAGES, 1):
        age = timedelta(days=-6, minutes=index * 7) if index <= 8 else timedelta(days=-1, minutes=(index - 8) * 10)
        echo_messages.append({"id": f"demo_echo_message_{index:02d}", "conversation_id": "demo_echo_conversation_main", "role": role, "content": content, "mode": mode, "timestamp": iso(age)})
    echo_profile_payload = {
        "status": "available", "message_count": 5,
        "profile_data": {
            "persona": {
                "identity": "一个在未来选择中寻找真实方向的年轻探索者",
                "traits": ["善于自省", "表达克制", "重视长期意义"],
                "emotion_pattern": ["面对外界期待时容易自我施压", "在不确定中反复确认选择是否真实"],
                "interests": ["温暖技术", "创造", "自我成长"],
                "values": ["真实体验", "创造价值", "按自己的速度成长"],
            },
            "communication_style": {"tone": "沉静、真诚、带有反思感"},
        },
    }
    echo_profiles = [{"id": "demo_echo_profile_main", "user_id": "demo_user_main", "profile_data": echo_profile_payload, "created_at": iso(timedelta(days=-1)), "updated_at": iso(timedelta(days=-1))}]

    agent_users = _load_agent_users()
    agent_profiles = [{
        "id": user["id"], "user_id": user["id"], "name": user["name"],
        "history_count": len(user.get("history", [])), **user["seed_profile"],
        "generated_by": "demo_seed", "updated_at": iso(timedelta(minutes=-30)),
    } for user in agent_users]
    agent_matches = [{
        "id": "demo_agent_match_yeve", "user_id": "yeve",
        "matches": [
            {"user_id": "kai", "agent": "Kai", "score": 88, "reason": ["共同关注技术、创造与未来", "都在快速变化中寻找方向", "都重视创造价值与持续成长"], "preview": "一个在快速变化中寻找真实技术价值的探索者"},
            {"user_id": "sora", "agent": "Sora", "score": 82, "reason": ["共同关注成长与自我探索", "都经历过选择方向时的迷茫", "都重视真实生活与按自己的速度成长"], "preview": "一个通过旅行与摄影记录生活、寻找方向的观察者"},
            {"user_id": "luna", "agent": "Luna", "score": 78, "reason": ["共同关注创造与真诚表达", "都期待作品和技术被认真理解", "都重视真实体验与人文温度"], "preview": "一个把细腻情绪写进音乐、坚持真诚表达的创作者"},
        ], "created_at": iso(timedelta(minutes=-30)),
    }]
    agent_dialogues = [{
        "id": "demo_agent_dialogue_yeve_kai", "user_id": "yeve", "target_user_id": "kai",
        "agent_a": "Yeve", "agent_b": "Kai", "score": 84,
        "reason": agent_matches[0]["matches"][0]["reason"],
        "conversation": [{"round": round_number, "from": name, "user_id": user_id, "text": text} for round_number, name, user_id, text in AGENT_DIALOGUE],
        "echo": "真正以人为本的技术，不只知道如何连接，也知道什么时候安静下来。",
        "created_at": iso(timedelta(minutes=-20)),
    }]

    return {
        "users": users, "bottles": bottles, "planes": planes,
        "comments": comments, "likes": likes, "capsules": capsules,
        "echo_conversations": echo_conversations, "echo_messages": echo_messages,
        "echo_profiles": echo_profiles, "agent_profiles": agent_profiles,
        "agent_matches": agent_matches, "agent_dialogues": agent_dialogues,
    }

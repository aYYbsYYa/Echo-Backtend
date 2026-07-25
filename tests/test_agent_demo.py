import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.services import agent_service
from app.storage.echo_storage import EchoStorage
from app.storage.json_repository import JsonRepository


class AgentDemoApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.original_repositories = (
            agent_service.profiles,
            agent_service.matches,
            agent_service.dialogues,
            agent_service.echo_storage,
        )
        agent_service.profiles = JsonRepository(root / "agent_profiles.json")
        agent_service.matches = JsonRepository(root / "agent_matches.json")
        agent_service.dialogues = JsonRepository(root / "agent_dialogues.json")
        agent_service.echo_storage = EchoStorage(root)

        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self) -> None:
        (
            agent_service.profiles,
            agent_service.matches,
            agent_service.dialogues,
            agent_service.echo_storage,
        ) = self.original_repositories
        self.temporary_directory.cleanup()

    def test_profile_uses_ai_json_and_hides_raw_history(self) -> None:
        model_profile = {
            "identity": "一个寻找技术与人文连接的创造者",
            "traits": ["理想主义", "好奇"],
            "emotion_pattern": ["期待理解", "偶尔焦虑"],
            "interests": ["AI", "创造"],
            "values": ["人文温度", "创造价值"],
            "tone": "温和、思考型",
        }
        with patch.object(
            agent_service,
            "chat_completion",
            return_value=json.dumps(model_profile, ensure_ascii=False),
        ) as complete:
            response = self.client.get("/api/agent/profile?user_id=yeve")

        body = response.get_json()["data"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["generated_by"], "ai")
        self.assertEqual(body["persona"]["identity"], model_profile["identity"])
        self.assertEqual(body["history_count"], 4)
        self.assertNotIn("history", body)
        complete.assert_called_once()

    def test_match_is_explainable_and_ranks_kai_first(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            response = self.client.post(
                "/api/agent/match",
                json={"user_id": "yeve", "limit": 3},
            )

        body = response.get_json()["data"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["matches"][0]["user_id"], "kai")
        self.assertNotIn("yeve", [item["user_id"] for item in body["matches"]])
        self.assertTrue(body["matches"][0]["reason"])
        self.assertEqual(len(agent_service.matches.all()), 1)

    def test_real_user_profile_drives_three_demo_matches(self) -> None:
        user_id = "usr_real"
        agent_service.echo_storage.save_profile(
            user_id,
            {
                "status": "available",
                "message_count": 6,
                "profile_data": {
                    "persona": {
                        "identity": "一个重视探索与成长的真实用户",
                        "traits": ["好奇", "克制"],
                        "emotion_pattern": ["期待理解", "未来焦虑"],
                        "interests": ["AI", "技术", "创造"],
                        "values": ["创造价值", "持续成长"],
                    },
                    "communication_style": {"tone": "温和直接"},
                },
            },
        )

        profile_response = self.client.get(f"/api/agent/profile?user_id={user_id}")
        match_response = self.client.post(
            "/api/agent/match", json={"user_id": user_id, "limit": 3}
        )

        profile = profile_response.get_json()["data"]
        matched_ids = {item["user_id"] for item in match_response.get_json()["data"]["matches"]}
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile["generated_by"], "echo_profile")
        self.assertEqual(profile["history_count"], 6)
        self.assertEqual(match_response.status_code, 200)
        self.assertEqual(matched_ids, {"sora", "luna", "kai"})
        self.assertNotIn("yeve", matched_ids)

    def test_real_user_without_profile_is_sent_to_echo(self) -> None:
        response = self.client.get("/api/agent/profile?user_id=usr_missing")

        self.assertEqual(response.status_code, 404)
        self.assertIn("请先去灵笺", response.get_json()["error"]["message"])

    def test_dialogue_runs_two_agents_then_generates_echo(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            agent_service.get_soul_profile("yeve")
            agent_service.get_soul_profile("kai")

        with patch.object(
            agent_service,
            "chat_completion",
            side_effect=[
                "A1：我的主人希望创造具有人文温度的技术。",
                "B1：我的主人也在寻找技术真正帮助人的方式。",
                "A2：技术需要在真实生活里回应人的处境。",
                "B2：我也重视那些缓慢但具体的改变。",
                "A3：愿我们继续认真理解技术背后的人。",
                "B3：也愿这份理解最终成为可以抵达的行动。",
                "你们都在让技术靠近真实的人。\n\n—— Yeve Echo",
            ],
        ) as complete:
            response = self.client.post(
                "/api/agent/dialogue",
                json={"user_id": "yeve", "target_user_id": "kai"},
            )

        body = response.get_json()["data"]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            [item["from"] for item in body["conversation"]],
            ["Yeve", "Kai", "Yeve", "Kai", "Yeve", "Kai"],
        )
        self.assertEqual(
            [item["round"] for item in body["conversation"]], [1, 1, 2, 2, 3, 3]
        )
        self.assertEqual(body["user_id"], "yeve")
        self.assertEqual(body["target_user_id"], "kai")
        self.assertIn("Yeve Echo", body["echo"])
        self.assertEqual(complete.call_count, 7)
        self.assertEqual(len(agent_service.dialogues.all()), 1)

    def test_fallback_dialogue_keeps_yeve_and_kai_rounds_distinct(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            result = agent_service.run_agent_dialogue("yeve", "kai")

        messages = result["conversation"]
        texts = [item["text"] for item in messages]
        self.assertEqual(len(set(texts)), 6)
        self.assertNotEqual(messages[2]["text"], messages[3]["text"])
        self.assertNotEqual(messages[4]["text"], messages[5]["text"])
        self.assertIn("成长", messages[2]["text"])
        self.assertIn("机器人", messages[3]["text"])
        self.assertIn("人文温度", messages[4]["text"])
        self.assertIn("探索未知", messages[5]["text"])

    def test_repeated_model_output_is_replaced_in_every_later_turn(self) -> None:
        repeated = "我们都想让技术真正靠近人的生活。"
        with patch.object(
            agent_service,
            "chat_completion",
            side_effect=[repeated, repeated, repeated, repeated, repeated, repeated, "最终回响"],
        ):
            result = agent_service.run_agent_dialogue("yeve", "kai")

        texts = [item["text"] for item in result["conversation"]]
        self.assertEqual(texts[0], repeated)
        self.assertEqual(len(set(texts)), 6)

    def test_repeated_model_output_cannot_collide_with_later_fallback(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            source = agent_service.get_soul_profile("yeve")
            target = agent_service.get_soul_profile("kai")
        repeated = agent_service._fallback_agent_message(
            target,
            source,
            round_number=1,
            speaker_position=1,
        )

        with patch.object(
            agent_service,
            "chat_completion",
            side_effect=[repeated, repeated, repeated, repeated, repeated, repeated, "最终回响"],
        ):
            result = agent_service.run_agent_dialogue("yeve", "kai")

        texts = [item["text"] for item in result["conversation"]]
        self.assertEqual(texts[0], repeated)
        self.assertEqual(len(set(texts)), 6)

    def test_short_high_similarity_message_is_rejected(self) -> None:
        history = [{"text": "我们都在寻找答案"}]

        self.assertTrue(
            agent_service._repeats_conversation("我们都在寻找答复", history)
        )

    def test_agent_message_replaces_punctuation_only_duplicate(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            source = agent_service.get_soul_profile("kai")
            target = agent_service.get_soul_profile("yeve")
        history = [
            {
                "round": 2,
                "from": "Yeve",
                "user_id": "yeve",
                "text": "我们想让技术真正靠近人的生活",
            }
        ]

        with patch.object(
            agent_service,
            "chat_completion",
            return_value="我们想让技术，真正靠近人的生活。",
        ):
            message = agent_service._agent_message(
                source,
                target,
                conversation=history,
                round_number=2,
                speaker_position=1,
            )

        self.assertNotEqual(message, "我们想让技术，真正靠近人的生活。")
        self.assertIn("机器人", message)

    def test_stream_dialogue_emits_each_message_then_persists(self) -> None:
        model_outputs = [
            "第一条表达",
            "第一条回应",
            "第二条表达",
            "第二条回应",
            "第三条表达",
            "第三条回应",
            "最终共同回响",
        ]
        with patch.object(
            agent_service, "chat_completion", side_effect=model_outputs
        ) as complete:
            response = self.client.post(
                "/api/agent/dialogue/stream",
                json={"user_id": "yeve", "target_user_id": "kai"},
            )
            response_text = response.get_data(as_text=True)

        events = [json.loads(line) for line in response_text.splitlines()]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/x-ndjson")
        self.assertEqual(
            [event["type"] for event in events],
            ["start", "message", "message", "message", "message", "message", "message", "echo", "done"],
        )
        messages = [event["data"] for event in events if event["type"] == "message"]
        self.assertEqual([item["round"] for item in messages], [1, 1, 2, 2, 3, 3])
        self.assertEqual(complete.call_count, 7)
        self.assertEqual(len(agent_service.dialogues.all()), 1)
        self.assertEqual(
            events[-1]["data"]["dialogue_id"], agent_service.dialogues.all()[0]["id"]
        )

    def test_interrupted_stream_does_not_persist_partial_dialogue(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value="一条表达"):
            events = agent_service.stream_agent_dialogue("yeve", "kai")
            self.assertEqual(next(events)["type"], "start")
            self.assertEqual(next(events)["type"], "message")
            events.close()

        self.assertEqual(agent_service.dialogues.all(), [])

    def test_dialogue_history_is_newest_first_and_supports_legacy_records(self) -> None:
        agent_service.dialogues.append(
            {
                "id": "legacy",
                "agent_a": "Yeve",
                "agent_b": "Kai",
                "conversation": [{"from": "Yeve", "user_id": "yeve", "text": "旧记录"}],
                "echo": "旧回响",
                "created_at": "2026-07-23T00:00:00+00:00",
            }
        )
        agent_service.dialogues.append(
            {
                "id": "new",
                "user_id": "yeve",
                "target_user_id": "sora",
                "agent_a": "Yeve",
                "agent_b": "Sora",
                "conversation": [],
                "echo": "新回响",
                "created_at": "2026-07-24T00:00:00+00:00",
            }
        )
        agent_service.dialogues.append(
            {
                "id": "unrelated",
                "user_id": "kai",
                "target_user_id": "sora",
                "conversation": [
                    {"from": "Legacy", "user_id": "yeve", "text": "冲突的旧字段"}
                ],
                "created_at": "2026-07-25T00:00:00+00:00",
            }
        )
        agent_service.dialogues.append(
            {
                "id": "damaged",
                "user_id": "kai",
                "conversation": None,
                "created_at": "2026-07-26T00:00:00+00:00",
            }
        )
        agent_service.dialogues.append(
            {
                "id": "null-owner",
                "user_id": None,
                "target_user_id": None,
                "conversation": [
                    {"from": "Legacy", "user_id": "yeve", "text": "不应回退"}
                ],
                "created_at": "2026-07-27T00:00:00+00:00",
            }
        )

        response = self.client.get("/api/agent/dialogues?user_id=yeve")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.get_json()["data"]], ["new", "legacy"])

    def test_dialogue_history_can_be_permanently_deleted(self) -> None:
        agent_service.dialogues.append(
            {
                "id": "legacy",
                "agent_a": "Yeve",
                "agent_b": "Kai",
                "conversation": [{"from": "Yeve", "user_id": "yeve", "text": "旧记录"}],
                "echo": "旧回响",
                "created_at": "2026-07-23T00:00:00+00:00",
            }
        )

        response = self.client.delete("/api/agent/dialogues/legacy?user_id=yeve")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], {"id": "legacy", "deleted": True})
        self.assertEqual(agent_service.dialogues.all(), [])
        self.assertIn("DELETE", response.headers["Access-Control-Allow-Methods"])

    def test_dialogue_delete_hides_unrelated_record_as_not_found(self) -> None:
        unrelated = {
            "id": "unrelated",
            "user_id": "kai",
            "target_user_id": "sora",
            "conversation": [
                {"from": "Legacy", "user_id": "yeve", "text": "冲突的旧字段"}
            ],
            "created_at": "2026-07-25T00:00:00+00:00",
        }
        agent_service.dialogues.append(unrelated)

        response = self.client.delete("/api/agent/dialogues/unrelated?user_id=yeve")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"]["message"], "未找到可删除的历史回响。"
        )
        self.assertEqual(agent_service.dialogues.all(), [unrelated])

    def test_dialogue_delete_does_not_fallback_when_owner_keys_are_null(self) -> None:
        record = {
            "id": "null-owner",
            "user_id": None,
            "target_user_id": None,
            "conversation": [
                {"from": "Legacy", "user_id": "yeve", "text": "不应回退"}
            ],
            "created_at": "2026-07-25T00:00:00+00:00",
        }
        agent_service.dialogues.append(record)

        response = self.client.delete("/api/agent/dialogues/null-owner?user_id=yeve")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(agent_service.dialogues.all(), [record])

    def test_profile_rejects_user_without_echo_profile(self) -> None:
        response = self.client.get("/api/agent/profile?user_id=unknown")

        self.assertEqual(response.status_code, 404)
        self.assertIn("请先去灵笺", response.get_json()["error"]["message"])

    def test_match_rejects_limit_outside_demo_pool(self) -> None:
        response = self.client.post(
            "/api/agent/match",
            json={"user_id": "yeve", "limit": 4},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["message"], "limit 必须是 1 到 3 的整数。"
        )

    def test_match_rejects_non_object_json(self) -> None:
        response = self.client.post("/api/agent/match", json=["yeve"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["message"], "请求体必须是 JSON 对象。"
        )

    def test_agent_message_rejects_contact_details(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            source = agent_service.get_soul_profile("yeve")
            target = agent_service.get_soul_profile("kai")

        with patch.object(
            agent_service,
            "chat_completion",
            return_value="加我微信 13800138000，我们私聊。",
        ):
            message = agent_service._agent_message(source, target)

        self.assertNotIn("微信", message)
        self.assertNotIn("13800138000", message)

    def test_profile_rejects_raw_history_and_retries_old_fallback(self) -> None:
        unsafe_profile = {
            "identity": "最近一直在思考，如何做一个真正帮助人的项目。",
            "traits": ["加我微信 13800138000"],
            "emotion_pattern": ["期待理解"],
            "interests": ["AI"],
            "values": ["创造价值"],
            "tone": "温和",
        }
        safe_profile = {
            "identity": "一个寻找技术人文价值的创造者",
            "traits": ["好奇", "克制"],
            "emotion_pattern": ["期待理解"],
            "interests": ["AI"],
            "values": ["创造价值"],
            "tone": "温和",
        }
        with (
            patch.object(Config, "AI_API_KEY", "test-key"),
            patch.object(Config, "AI_API_URL", "https://example.com"),
            patch.object(Config, "AI_MODEL", "test-model"),
            patch.object(
                agent_service,
                "chat_completion",
                return_value=json.dumps(unsafe_profile, ensure_ascii=False),
            ),
        ):
            first = agent_service.get_soul_profile("yeve")

        self.assertNotEqual(first["persona"]["identity"], unsafe_profile["identity"])
        self.assertNotIn("微信", "".join(first["persona"]["traits"]))

        first["generated_by"] = "demo_fallback"
        first["updated_at"] = "2020-01-01T00:00:00+00:00"
        agent_service.profiles.upsert(first)
        with (
            patch.object(Config, "AI_API_KEY", "test-key"),
            patch.object(Config, "AI_API_URL", "https://example.com"),
            patch.object(Config, "AI_MODEL", "test-model"),
            patch.object(
                agent_service,
                "chat_completion",
                return_value=json.dumps(safe_profile, ensure_ascii=False),
            ) as complete,
        ):
            refreshed = agent_service.get_soul_profile("yeve")

        self.assertEqual(refreshed["generated_by"], "ai")
        self.assertEqual(refreshed["persona"]["identity"], safe_profile["identity"])
        complete.assert_called_once()

    def test_profile_rejects_identity_age_and_precise_location(self) -> None:
        unsafe_profile = {
            "identity": "我叫张三，今年 22 岁，住在杭州市西湖区",
            "traits": ["好奇", "克制"],
            "emotion_pattern": ["期待理解"],
            "interests": ["AI"],
            "values": ["创造价值"],
            "tone": "温和",
        }
        with patch.object(
            agent_service,
            "chat_completion",
            return_value=json.dumps(unsafe_profile, ensure_ascii=False),
        ):
            profile = agent_service.get_soul_profile("yeve")

        self.assertNotIn("张三", profile["persona"]["identity"])
        self.assertNotIn("西湖区", profile["persona"]["identity"])

    def test_invalid_nonempty_profile_json_is_fallback(self) -> None:
        with patch.object(
            agent_service,
            "chat_completion",
            return_value='{"unexpected": "value"}',
        ):
            profile = agent_service.get_soul_profile("yeve")

        self.assertEqual(profile["generated_by"], "demo_fallback")

    def test_dialogue_without_target_only_makes_seven_model_calls(self) -> None:
        with patch.object(
            agent_service,
            "chat_completion",
            side_effect=[
                "Soul A 第一轮表达",
                "Soul B 第一轮回应",
                "Soul A 第二轮表达",
                "Soul B 第二轮回应",
                "Soul A 第三轮表达",
                "Soul B 第三轮回应",
                "共同回响",
            ],
        ) as complete:
            response = self.client.post("/api/agent/dialogue", json={"user_id": "yeve"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["data"]["agent_b"], "Kai")
        self.assertEqual(complete.call_count, 7)


class JsonRepositoryConcurrencyTests(unittest.TestCase):
    def test_concurrent_append_keeps_every_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonRepository(Path(directory) / "records.json")

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(
                    executor.map(
                        lambda value: repository.append({"id": str(value)}),
                        range(40),
                    )
                )

            self.assertEqual(len(repository.all()), 40)


if __name__ == "__main__":
    unittest.main()

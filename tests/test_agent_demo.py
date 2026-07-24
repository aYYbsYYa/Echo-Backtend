import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.services import agent_service
from app.storage.json_repository import JsonRepository


class AgentDemoApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.original_repositories = (
            agent_service.profiles,
            agent_service.matches,
            agent_service.dialogues,
        )
        agent_service.profiles = JsonRepository(root / "agent_profiles.json")
        agent_service.matches = JsonRepository(root / "agent_matches.json")
        agent_service.dialogues = JsonRepository(root / "agent_dialogues.json")

        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self) -> None:
        (
            agent_service.profiles,
            agent_service.matches,
            agent_service.dialogues,
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

    def test_dialogue_runs_two_agents_then_generates_echo(self) -> None:
        with patch.object(agent_service, "chat_completion", return_value=None):
            agent_service.get_soul_profile("yeve")
            agent_service.get_soul_profile("kai")

        with patch.object(
            agent_service,
            "chat_completion",
            side_effect=[
                "我的主人希望创造具有人文温度的技术。",
                "我的主人也在寻找技术真正帮助人的方式。",
                "你们都在让技术靠近真实的人。\n\n—— Yeve Echo",
            ],
        ) as complete:
            response = self.client.post(
                "/api/agent/dialogue",
                json={"user_id": "yeve", "target_user_id": "kai"},
            )

        body = response.get_json()["data"]
        self.assertEqual(response.status_code, 201)
        self.assertEqual([item["from"] for item in body["conversation"]], ["Yeve", "Kai"])
        self.assertIn("Yeve Echo", body["echo"])
        self.assertEqual(complete.call_count, 3)
        self.assertEqual(len(agent_service.dialogues.all()), 1)

    def test_profile_rejects_unknown_demo_agent(self) -> None:
        response = self.client.get("/api/agent/profile?user_id=unknown")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"]["message"], "未找到这个 Demo Soul Agent。"
        )

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

    def test_dialogue_without_target_only_makes_three_model_calls(self) -> None:
        with patch.object(
            agent_service,
            "chat_completion",
            side_effect=["Soul A 表达", "Soul B 回应", "共同回响"],
        ) as complete:
            response = self.client.post("/api/agent/dialogue", json={"user_id": "yeve"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["data"]["agent_b"], "Kai")
        self.assertEqual(complete.call_count, 3)


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

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.bottle import bottle_api
from app.config import Config
from app.plane import plane_api
from app.services import ai_service
from app.storage.json_repository import JsonRepository


class ApiFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.users = JsonRepository(root / "users.json")
        self.bottles = JsonRepository(root / "bottles.json")
        self.planes = JsonRepository(root / "planes.json")
        self.comments = JsonRepository(root / "comments.json")
        self.likes = JsonRepository(root / "likes.json")
        self.users.append(
            {
                "id": "usr_author",
                "nickname": "海风",
                "birthday": "2000-01-01",
                "gender": "unknown",
                "region": "杭州",
                "avatar": "海",
            }
        )
        self.users.append(
            {
                "id": "usr_reader",
                "nickname": "远岸",
                "birthday": "2001-01-01",
                "gender": "unknown",
                "region": "上海",
                "avatar": "远",
            }
        )

        self.original_repositories = (
            bottle_api.users,
            bottle_api.bottles,
            bottle_api.comments,
            bottle_api.likes,
            plane_api.users,
            plane_api.planes,
        )
        bottle_api.users = self.users
        bottle_api.bottles = self.bottles
        bottle_api.comments = self.comments
        bottle_api.likes = self.likes
        plane_api.users = self.users
        plane_api.planes = self.planes

        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self) -> None:
        (
            bottle_api.users,
            bottle_api.bottles,
            bottle_api.comments,
            bottle_api.likes,
            plane_api.users,
            plane_api.planes,
        ) = self.original_repositories
        self.temporary_directory.cleanup()

    def add_bottle(self, user_id: str = "usr_author") -> dict:
        item = {
            "id": "bottle_test",
            "content": "一条测试内容",
            "user_id": user_id,
            "region": "杭州",
            "created_at": "2026-07-20T00:00:00+00:00",
            "tags": ["日常"],
            "views": 0,
            "reply": None,
        }
        self.bottles.append(item)
        return item

    def test_discovery_keeps_self_content_out_of_candidates(self) -> None:
        self.add_bottle()
        self.planes.append(
            {
                "id": "plane_test",
                "content": "一架测试纸飞机",
                "user_id": "usr_author",
                "region": "杭州",
                "created_at": "2026-07-20T00:00:00+00:00",
                "tags": ["日常"],
                "scene": "sky",
                "views": 0,
            }
        )

        bottle_response = self.client.get("/api/bottles/discover?user_id=usr_author&mode=random")
        plane_response = self.client.get("/api/planes/discover?user_id=usr_author")

        self.assertIsNone(bottle_response.get_json()["data"])
        self.assertEqual(bottle_response.get_json()["message"], "海面暂时安静，稍后再来。")
        self.assertIsNone(plane_response.get_json()["data"])
        self.assertEqual(plane_response.get_json()["message"], "风里还没有新的纸飞机。")

    def test_comment_persists_nickname_and_timestamp_for_author(self) -> None:
        self.add_bottle()

        response = self.client.post(
            "/api/bottles/bottle_test/comments",
            json={"user_id": "usr_reader", "content": "愿你今晚睡个好觉。"},
        )
        author_view = self.client.get("/api/bottles/bottle_test?user_id=usr_author").get_json()["data"]

        self.assertEqual(response.status_code, 201)
        self.assertEqual(author_view["comments"][0]["nickname"], "远岸")
        self.assertTrue(author_view["comments"][0]["created_at"])

    def test_plane_detail_returns_scene_and_author_flag(self) -> None:
        self.planes.append(
            {
                "id": "plane_test",
                "content": "一架测试纸飞机",
                "user_id": "usr_author",
                "region": "杭州",
                "created_at": "2026-07-20T00:00:00+00:00",
                "tags": ["日常"],
                "scene": "sky",
                "views": 2,
            }
        )

        response = self.client.get("/api/planes/plane_test?user_id=usr_author")
        body = response.get_json()["data"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["scene"], "sky")
        self.assertTrue(body["is_author"])

    def test_plane_publish_generates_developer_reply(self) -> None:
        with patch.object(plane_api, "generate_developer_reply", return_value="纸飞机的模型回信") as generate:
            response = self.client.post(
                "/api/planes",
                json={"user_id": "usr_author", "content": "把一句晚安交给风。"},
            )

        body = response.get_json()["data"]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body["reply"], "纸飞机的模型回信")
        generate.assert_called_once_with("海风", "杭州", "把一句晚安交给风。")

    def test_bottle_publish_uses_ai_reply_without_moderation_response(self) -> None:
        with patch.object(bottle_api, "generate_developer_reply", return_value="模型生成的回信") as generate:
            response = self.client.post(
                "/api/bottles",
                json={"user_id": "usr_author", "content": "包含赌博一词但不再经过发布审核。"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body["data"]["reply"], "模型生成的回信")
        self.assertNotIn("review", body)
        generate.assert_called_once_with("海风", "杭州", "包含赌博一词但不再经过发布审核。")


class AiServiceTests(unittest.TestCase):
    def test_openai_chat_completions_request_and_response(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {"choices": [{"message": {"content": " 来自模型的回信 "}}]},
                    ensure_ascii=False,
                ).encode("utf-8")

        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

        with (
            patch.object(Config, "AI_API_KEY", "test-key"),
            patch.object(Config, "AI_API_URL", "https://example.com"),
            patch.object(Config, "AI_MODEL", "test-model"),
            patch.object(ai_service, "urlopen", side_effect=fake_urlopen),
        ):
            reply = ai_service.generate_developer_reply("海风", "杭州", "测试内容")

        request = captured["request"]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(reply, "来自模型的回信")
        self.assertEqual(request.full_url, "https://example.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        self.assertEqual(captured["timeout"], 20)

    def test_invalid_ai_url_does_not_raise(self) -> None:
        with (
            patch.object(Config, "AI_API_KEY", "test-key"),
            patch.object(Config, "AI_API_URL", "not a valid url"),
            patch.object(Config, "AI_MODEL", "test-model"),
        ):
            self.assertIsNone(ai_service.generate_developer_reply("海风", "杭州", "测试内容"))


if __name__ == "__main__":
    unittest.main()

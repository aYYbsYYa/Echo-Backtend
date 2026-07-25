import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.bottle import bottle_api
from app.capsule import capsule_api
from app.config import Config
from app.demo_seed.seed_runner import EXPECTED_COUNTS, reset_and_seed_demo_data
from app.echo import echo_api
from app.plane import plane_api
from app.storage.capsule_storage import CapsuleStorage
from app.storage.echo_storage import EchoStorage
from app.storage.json_repository import JsonRepository
from app.storage.user_storage import UserStorage
from app.user import user_api


class DemoSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.data_dir = self.root / "data"
        self.upload_dir = self.data_dir / "uploads"
        self.config_patches = (
            patch.object(Config, "DATA_DIR", self.data_dir),
            patch.object(Config, "UPLOAD_DIR", self.upload_dir),
            patch.object(Config, "DEMO_RESET_ON_START", False),
        )
        for config_patch in self.config_patches:
            config_patch.start()

    def tearDown(self) -> None:
        for config_patch in reversed(self.config_patches):
            config_patch.stop()
        self.temporary_directory.cleanup()

    def _records(self, collection: str) -> list[dict]:
        return json.loads((self.data_dir / f"{collection}.json").read_text(encoding="utf-8"))

    def _bind_api_repositories(self) -> None:
        users = UserStorage()
        comments = JsonRepository(self.data_dir / "comments.json")
        likes = JsonRepository(self.data_dir / "likes.json")
        bottle_api.users = users
        bottle_api.bottles = JsonRepository(self.data_dir / "bottles.json")
        bottle_api.comments = comments
        bottle_api.likes = likes
        plane_api.users = users
        plane_api.planes = JsonRepository(self.data_dir / "planes.json")
        plane_api.comments = comments
        plane_api.likes = likes
        capsule_api.users = users
        capsule_api.capsules = CapsuleStorage()
        capsule_api.IMAGE_DIR = self.data_dir / "capsule_images"
        user_api.users = users
        echo_api.storage = EchoStorage(self.data_dir)

    def test_reset_is_repeatable_and_recalculates_relative_times(self) -> None:
        first_now = datetime(2026, 7, 25, 8, 0, tzinfo=timezone.utc)
        second_now = first_now + timedelta(hours=2)
        reset_and_seed_demo_data(first_now)
        first_ids = {
            name: [item["id"] for item in self._records(name)]
            for name in Config.JSON_FILES
        }

        JsonRepository(self.data_dir / "users.json").append({"id": "temporary"})
        self.upload_dir.joinpath("temporary.png").write_bytes(b"temporary")
        reset_and_seed_demo_data(second_now)

        for name, expected_count in EXPECTED_COUNTS.items():
            records = self._records(name)
            self.assertEqual(len(records), expected_count)
            self.assertEqual([item["id"] for item in records], first_ids[name])
        soon = next(item for item in self._records("capsules") if item["id"] == "demo_capsule_soon")
        self.assertEqual(datetime.fromisoformat(soon["unlock_at"]), second_now + timedelta(seconds=10))
        self.assertFalse((self.upload_dir / "temporary.png").exists())
        self.assertEqual(
            {path.name for path in self.upload_dir.iterdir()},
            {"demo_rainy_walk.jpeg", "demo_sunset.png"},
        )

    def test_existing_apis_expose_main_demo_content_and_assets(self) -> None:
        reset_and_seed_demo_data(datetime.now(timezone.utc))
        self._bind_api_repositories()
        app = create_app()
        client = app.test_client()

        user = client.get("/api/users/demo_user_main")
        bottles = client.get("/api/bottles/mine/demo_user_main")
        planes = client.get("/api/planes/mine/demo_user_main")
        capsules = client.get("/api/capsules/mine/demo_user_main")
        profile = client.get("/api/echo/users/demo_user_main/profile")
        bottle_image = client.get("/api/bottles/demo_bottle_10?user_id=demo_user_main")
        plane_image = client.get("/api/planes/demo_plane_03?user_id=demo_user_main")

        self.assertEqual(user.status_code, 200)
        self.assertEqual(user.get_json()["data"]["nickname"], "林间旅人")
        self.assertEqual(len(bottles.get_json()["data"]), 2)
        self.assertEqual(len(planes.get_json()["data"]), 2)
        bottle_01 = next(item for item in bottles.get_json()["data"] if item["id"] == "demo_bottle_01")
        self.assertEqual(bottle_01["likes"], 6)
        self.assertEqual(len(bottle_01["comments"]), 3)
        self.assertTrue(bottle_01["reply"])
        capsule_data = capsules.get_json()["data"]
        self.assertEqual(len(capsule_data), 4)
        self.assertTrue(any(item["opened_at"] for item in capsule_data))
        self.assertTrue(any(item["is_unlocked"] and not item["opened_at"] for item in capsule_data))
        self.assertTrue(any(not item["is_unlocked"] for item in capsule_data))
        self.assertEqual(profile.get_json()["data"]["status"], "available")
        self.assertEqual(bottle_image.get_json()["data"]["image_url"], "/api/uploads/demo_rainy_walk.jpeg")
        self.assertEqual(plane_image.get_json()["data"]["image_url"], "/api/uploads/demo_sunset.png")
        image_response = client.get("/api/uploads/demo_sunset.png")
        try:
            self.assertEqual(image_response.status_code, 200)
        finally:
            image_response.close()

    def test_private_feedback_is_hidden_from_other_users(self) -> None:
        reset_and_seed_demo_data(datetime.now(timezone.utc))
        self._bind_api_repositories()
        client = create_app().test_client()

        response = client.get("/api/bottles/demo_bottle_01?user_id=demo_user_wind")
        data = response.get_json()["data"]
        self.assertIsNone(data["reply"])
        self.assertNotIn("comments", data)
        self.assertNotIn("likes", data)

    def test_create_app_runs_seed_once_when_enabled(self) -> None:
        with (
            patch.object(Config, "DEMO_RESET_ON_START", True),
            patch("app.demo_seed.reset_and_seed_demo_data") as reset,
        ):
            create_app()
        reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

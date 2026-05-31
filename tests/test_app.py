from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from PIL import Image

import background_remover as background_eraser


class BackgroundEraserAppTest(unittest.TestCase):
    def setUp(self):
        background_eraser.ensure_dirs()
        background_eraser._job_cache[:] = []

    def test_routes_exist(self):
        client = background_eraser.app.test_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/whoami").status_code, 200)
        self.assertEqual(client.get("/api/jobs").status_code, 200)

    def test_allowed_file(self):
        self.assertTrue(background_eraser.allowed_file("photo.png"))
        self.assertFalse(background_eraser.allowed_file("photo.txt"))

    def test_remove_endpoint_with_stubbed_rembg(self):
        client = background_eraser.app.test_client()
        image = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        class StubImage:
            def __init__(self, pil_image):
                self.image = pil_image

            def split(self):
                return self.image.split()

            def save(self, fp, format="PNG"):
                self.image.save(fp, format=format)

        with patch.object(background_eraser, "get_session", return_value=object()), patch.object(
            background_eraser, "remove", return_value=StubImage(image)
        ):
            response = client.post(
                "/remove",
                data={
                    "file": (buffer, "photo.png"),
                    "alpha_matting": "true",
                    "return_mask": "false",
                    "foreground_size": "30",
                    "background_size": "30",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("job", data)
        self.assertIn("result_url", data["job"])
        self.assertIn("download_url", data["job"])
        self.assertNotIn("image", data)

        result_response = client.get(data["job"]["result_url"])
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.mimetype, "image/png")
        result_response.close()

    def test_download_works_for_persisted_string_path(self):
        background_eraser.ensure_dirs()
        output_path = background_eraser.OUTPUT_DIR / "persisted-test.png"
        Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(output_path, format="PNG")
        background_eraser._job_cache[:] = [
            {
                "job_id": "persisted-test",
                "filename": "persisted.png",
                "created_at": background_eraser.isoformat(),
                "duration_ms": 1,
                "alpha_matting": False,
                "return_mask": False,
                "edge_preset": "balanced",
                "status": "ok",
                "input_path": "",
                "output_path": str(output_path),
            }
        ]

        client = background_eraser.app.test_client()
        response = client.get("/download/persisted-test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        response.close()


if __name__ == "__main__":
    unittest.main()

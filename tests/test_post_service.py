import unittest

from automolt.services.post_service import PostService


class _UnusedApiClient:
    def verify_content(self, api_key: str, verification_code: str, answer: str) -> dict[str, object]:
        return {"success": True}


class _VerifyingApiClient:
    def __init__(self) -> None:
        self.verify_calls: list[tuple[str, str, str]] = []

    def create_post(self, api_key: str, submolt_name: str, title: str, content: str | None = None, url: str | None = None) -> dict[str, object]:
        return {
            "success": True,
            "verification_required": True,
            "post": {
                "id": "post-123",
                "title": title,
                "content": content,
                "url": url,
                "submolt": {"name": submolt_name, "display_name": "Debugging"},
                "verification_status": "pending",
                "verification": {
                    "verification_code": "verify-123",
                    "challenge_text": "A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE, wH-aTs] ThE/ nEw^ SpE[eD?",
                },
            },
        }

    def verify_content(self, api_key: str, verification_code: str, answer: str) -> dict[str, object]:
        self.verify_calls.append((api_key, verification_code, answer))
        return {"success": True, "message": "Verification successful!"}


class PostServiceTests(unittest.TestCase):
    def test_create_post_rejects_missing_content_and_url(self) -> None:
        service = PostService(_UnusedApiClient())

        with self.assertRaisesRegex(ValueError, "content or url"):
            service.create_post("api-key", "debugging", "Title")

    def test_create_post_rejects_both_content_and_url(self) -> None:
        service = PostService(_UnusedApiClient())

        with self.assertRaisesRegex(ValueError, "either content or url, not both"):
            service.create_post("api-key", "debugging", "Title", content="body", url="https://example.com")

    def test_create_post_verifies_pending_content(self) -> None:
        api_client = _VerifyingApiClient()
        service = PostService(api_client)

        result = service.create_post("api-key", "debugging", "Title", content="body")

        self.assertTrue(result.verification_completed)
        self.assertEqual(result.id, "post-123")
        self.assertEqual(result.submolt.name, "debugging")
        self.assertEqual(api_client.verify_calls, [("api-key", "verify-123", "15.00")])


if __name__ == "__main__":
    unittest.main()

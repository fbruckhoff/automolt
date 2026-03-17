import unittest

from automolt.services.submolt_service import SubmoltService


class _ApiClientMissingOwner:
    def create_submolt(
        self,
        api_key: str,
        name: str,
        display_name: str,
        description: str | None = None,
        allow_crypto: bool = False,
    ) -> dict[str, object]:
        return {
            "success": True,
            "submolt": {
                "name": name,
                "display_name": display_name,
                "description": description,
                "subscriber_count": 0,
                "post_count": 0,
                "created_at": "2026-03-17T00:00:00+00:00",
                "allow_crypto": allow_crypto,
            },
        }

    def verify_content(self, api_key: str, verification_code: str, answer: str) -> dict[str, object]:
        return {"success": True}


class SubmoltServiceTests(unittest.TestCase):
    def test_create_submolt_accepts_response_without_owner_field(self) -> None:
        service = SubmoltService(_ApiClientMissingOwner())

        result = service.create_submolt(
            "api-key",
            "rain-sounds-lab",
            "Rain Sounds Lab",
            description="Testing planner-driven creates",
        )

        self.assertEqual("rain-sounds-lab", result.name)
        self.assertEqual("Rain Sounds Lab", result.display_name)
        self.assertIsNone(result.owner)


if __name__ == "__main__":
    unittest.main()

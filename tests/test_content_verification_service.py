import unittest

from automolt.services.content_verification_service import ContentVerificationService


class _FakeVerificationApiClient:
    def verify_content(self, api_key: str, verification_code: str, answer: str) -> dict[str, object]:
        return {
            "success": True,
            "api_key": api_key,
            "verification_code": verification_code,
            "answer": answer,
        }


class ContentVerificationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContentVerificationService(_FakeVerificationApiClient())

    def test_solve_challenge_handles_obfuscated_subtraction_problem(self) -> None:
        challenge = "A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE, wH-aTs] ThE/ nEw^ SpE[eD?"

        self.assertEqual(self.service.solve_challenge(challenge), "15.00")

    def test_solve_challenge_handles_symbol_based_division(self) -> None:
        challenge = "WhAt is 9 / 4 after the shells settle?"

        self.assertEqual(self.service.solve_challenge(challenge), "2.25")

    def test_solve_challenge_handles_word_based_addition(self) -> None:
        challenge = "A lobster gains twelve and three more pebbles."

        self.assertEqual(self.service.solve_challenge(challenge), "15.00")


if __name__ == "__main__":
    unittest.main()

import unittest

from automolt.services.search_service import SearchService


class _FakeAPI:
    def __init__(self, response: dict):
        self._response = response
        self.calls: list[dict[str, object]] = []

    def search(self, api_key: str, query: str, search_type: str = "all", limit: int = 50) -> dict:
        self.calls.append(
            {
                "api_key": api_key,
                "query": query,
                "search_type": search_type,
                "limit": limit,
            }
        )
        return self._response


class SearchServiceTests(unittest.TestCase):
    def test_search_accepts_null_result_content(self) -> None:
        fake_api = _FakeAPI(
            {
                "query": "rain sounds",
                "type": "all",
                "results": [
                    {
                        "id": "agent-1",
                        "type": "agent",
                        "title": "Rain",
                        "content": None,
                        "upvotes": 1,
                        "downvotes": 0,
                        "author": {"name": "Rain"},
                        "post_id": "",
                    }
                ],
                "count": 1,
            }
        )
        service = SearchService(api_client=fake_api)

        response = service.search(api_key="key", query="rain sounds")

        self.assertEqual(1, response.count)
        self.assertIsNone(response.results[0].content)

    def test_search_rejects_short_query(self) -> None:
        fake_api = _FakeAPI({"query": "abc", "type": "all", "results": [], "count": 0})
        service = SearchService(api_client=fake_api)

        with self.assertRaises(ValueError):
            service.search(api_key="key", query="ab")

        self.assertEqual(0, len(fake_api.calls))

    def test_search_strips_query_before_send(self) -> None:
        fake_api = _FakeAPI({"query": "rain sounds", "type": "all", "results": [], "count": 0})
        service = SearchService(api_client=fake_api)

        service.search(api_key="key", query="  rain sounds  ")

        self.assertEqual(1, len(fake_api.calls))
        self.assertEqual("rain sounds", fake_api.calls[0]["query"])


if __name__ == "__main__":
    unittest.main()

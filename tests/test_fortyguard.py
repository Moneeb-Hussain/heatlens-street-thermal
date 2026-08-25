import httpx

from heatlens.clients.fortyguard import FortyGuardClient, city_mean_from_stats
from heatlens.domain.cities import get_city


def test_heatmap_submit_and_poll(tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path == "/v1/heatmap":
            return httpx.Response(200, json={"error": False, "data": {"activity_id": "act-1"}})
        if request.url.path == "/v1/status/act-1":
            return httpx.Response(
                200,
                json={
                    "error": False,
                    "data": {
                        "status": "Completed",
                        "result": {"stats_data": {"Temperature_stats": {"Mean": 42.5}}},
                    },
                },
            )
        return httpx.Response(404, json={"error": True})

    transport = httpx.MockTransport(handler)
    client = FortyGuardClient("test-key", "https://api.fortyguard.com", transport=transport)
    try:
        result = client.heatmap(get_city("phoenix"), start_date="2024-07-15", start_time="14:00", max_polls=3, poll_seconds=0)
        assert city_mean_from_stats(result) == 42.5
        assert calls["n"] == 2
    finally:
        client.close()

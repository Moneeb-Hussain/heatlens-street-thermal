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


def test_heatmap_poll_retries_through_transient_404(tmp_path):
    """A freshly submitted activity can 404 on the first poll(s) before the
    server indexes it (seen on newly created FortyGuard accounts). The
    client should retry rather than fail immediately."""
    status_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/heatmap":
            return httpx.Response(200, json={"error": False, "data": {"activity_id": "act-2"}})
        if request.url.path == "/v1/status/act-2":
            status_calls["n"] += 1
            if status_calls["n"] < 3:
                return httpx.Response(404, json={"error": True, "message": "Activity not found"})
            return httpx.Response(
                200,
                json={
                    "error": False,
                    "data": {
                        "status": "Completed",
                        "result": {"stats_data": {"Temperature_stats": {"Mean": 30.0}}},
                    },
                },
            )
        return httpx.Response(404, json={"error": True})

    transport = httpx.MockTransport(handler)
    client = FortyGuardClient("test-key", "https://api.fortyguard.com", transport=transport)
    try:
        result = client.heatmap(
            get_city("phoenix"), start_date="2024-07-15", start_time="14:00", max_polls=5, poll_seconds=0
        )
        assert city_mean_from_stats(result) == 30.0
        assert status_calls["n"] == 3
    finally:
        client.close()


def test_heatmap_poll_gives_up_on_persistent_404(tmp_path):
    """If the activity never becomes queryable within max_polls, still fail
    (don't retry forever) -- with a message that distinguishes this from a
    real activity failure."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/heatmap":
            return httpx.Response(200, json={"error": False, "data": {"activity_id": "act-3"}})
        if request.url.path == "/v1/status/act-3":
            return httpx.Response(404, json={"error": True, "message": "Activity not found"})
        return httpx.Response(404, json={"error": True})

    transport = httpx.MockTransport(handler)
    client = FortyGuardClient("test-key", "https://api.fortyguard.com", transport=transport)
    try:
        try:
            client.heatmap(
                get_city("phoenix"), start_date="2024-07-15", start_time="14:00", max_polls=3, poll_seconds=0
            )
            assert False, "expected UpstreamError"
        except Exception as exc:
            assert "never became queryable" in str(exc)
    finally:
        client.close()

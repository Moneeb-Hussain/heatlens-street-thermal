import json

from fastapi.testclient import TestClient

from api import deps
from api.main import create_app
from heatlens.domain.types import StreetSegment, UrbanFormFeatures
from heatlens.store import JsonSegmentStore


def _client(tmp_path, monkeypatch, coefficients=None, segments=None):
    # Isolate from a real .env in the repo root — heatlens.config._load_dotenv()
    # reads whatever .env is in cwd, which would silently undo delenv() below.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEATLENS_SEGMENTS_PATH", str(tmp_path / "segments.json"))
    monkeypatch.setenv("HEATLENS_COEFFICIENTS_PATH", str(tmp_path / "coefficients.json"))
    monkeypatch.setenv("HEATLENS_CACHE_PATH", str(tmp_path / "cache.sqlite"))
    monkeypatch.setenv("HEATLENS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.delenv("FORTYGUARD_API_KEY", raising=False)
    monkeypatch.delenv("FORTYGUARD_API_KEY_ATLANTA", raising=False)
    monkeypatch.delenv("FORTYGUARD_API_KEY_CHICAGO", raising=False)
    monkeypatch.delenv("MAPILLARY_ACCESS_TOKEN", raising=False)
    if coefficients is not None:
        (tmp_path / "coefficients.json").write_text(json.dumps(coefficients), encoding="utf-8")
    if segments is not None:
        JsonSegmentStore(tmp_path / "segments.json").write_segments(segments)
    deps.get_settings.cache_clear()
    deps.get_cache.cache_clear()
    return TestClient(create_app())


def _seg():
    return StreetSegment(
        image_id="px-1",
        lat=33.45,
        lon=-112.07,
        city="phoenix",
        block_id="b_1",
        delta_t=4.2,
        features=UrbanFormFeatures(0.05, 0.6, 0.2, 0.15),
        split="train",
        source="fortyguard",
        validated=True,
    )


def test_health_and_cities(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["capabilities"]["fortyguard"] is False
    cities = client.get("/cities").json()["cities"]
    assert {row["id"] for row in cities} >= {"phoenix", "miami", "karachi"}


def test_unknown_city_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get("/segments", params={"city": "narnia"})
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_segments_empty_without_dataset(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get("/segments", params={"city": "phoenix"})
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_segments_from_store(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, segments=[_seg()])
    response = client.get("/segments", params={"city": "phoenix"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["segments"][0]["delta_t"] == 4.2
    assert data["segments"][0]["validated"] is True


def test_forecast_without_key_is_503(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get("/forecast", params={"city": "phoenix"})
    assert response.status_code == 503
    assert response.json()["code"] == "FORTYGUARD_NOT_CONFIGURED"


def test_predict_rejects_non_image(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post("/predict", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_predict_image_without_model_is_503(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post("/predict", files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_NOT_AVAILABLE"


def test_predict_features_requires_coefficients(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/predict/features",
        json={"canopy_frac": 0.4, "asphalt_frac": 0.2, "sky_frac": 0.2, "building_frac": 0.2},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "COEFFICIENTS_NOT_AVAILABLE"


def test_predict_features_with_coefficients(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        coefficients={"intercept": 0, "canopy": -4, "asphalt": 2, "sky": 0, "building": 0},
    )
    response = client.post(
        "/predict/features",
        json={"canopy_frac": 0.5, "asphalt_frac": 0.25, "sky_frac": 0.1, "building_frac": 0.1},
    )
    assert response.status_code == 200
    assert response.json()["model"] == "linear_features_b1"
    assert abs(response.json()["delta_t"] - (-1.5)) < 1e-9


def test_validate_fills_predicted_when_coefficients_exist(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        coefficients={"intercept": 0, "canopy": -4, "asphalt": 2, "sky": 0, "building": 0},
        segments=[_seg()],
    )
    response = client.get("/validate", params={"city": "phoenix"})
    assert response.status_code == 200
    pair = response.json()["pairs"][0]
    assert pair["reference_delta_t"] == 4.2
    assert pair["predicted_delta_t"] is not None
    # 0 + (-4)*0.05 + 2*0.6 = 1.0
    assert abs(pair["predicted_delta_t"] - 1.0) < 1e-9


def test_street_name_endpoint(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "heatlens.clients.nominatim.NominatimClient.street_name",
        lambda self, lat, lon: "W Van Buren St & S 15th Ave",
    )
    response = client.get("/street-name", params={"lat": 33.4484, "lon": -112.074})
    assert response.status_code == 200
    assert response.json()["street"] == "W Van Buren St & S 15th Ave"


def test_recommend_ranks(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        coefficients={"intercept": 0, "canopy": -8, "asphalt": 0, "sky": 0, "building": 0, "target_canopy_frac": 0.4},
        segments=[_seg()],
    )
    response = client.get("/recommend", params={"city": "phoenix"})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["indicative"] is True
    assert item["estimated_cooling_c"] > 0

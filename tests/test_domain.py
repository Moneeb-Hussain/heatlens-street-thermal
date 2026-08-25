from datetime import datetime, timezone

from heatlens.domain.cities import get_city
from heatlens.domain.types import Coefficients, StreetSegment, UrbanFormFeatures
from heatlens.ingest.filters import is_usable_image
from heatlens.ingest.grid import GRID_SPACING_M, block_id, grid_centroids, metres_to_degrees
from heatlens.ml.linear import LinearFeatureRegressor
from heatlens.ml.metrics import mae, r_squared, spearman_rho, top_decile_precision
from heatlens.ml.splits import leakage_report
from heatlens.services.fusion import fuse_absolute, nearest_forecast
from heatlens.services.recommend import estimated_delta_t, rank_interventions
from heatlens.domain.types import ForecastPoint


def _segment(city="phoenix", block="b_1", split="train", canopy=0.1, delta=4.0, image="img-1"):
    return StreetSegment(
        image_id=image,
        lat=33.45,
        lon=-112.07,
        city=city,
        block_id=block,
        delta_t=delta,
        features=UrbanFormFeatures(
            canopy_frac=canopy,
            asphalt_frac=0.5,
            sky_frac=0.2,
            building_frac=0.2,
        ),
        split=split,
        source="fortyguard",
        validated=True,
    )


def test_fuse_absolute():
    assert fuse_absolute(40.0, -3.0) == 37.0


def test_nearest_forecast():
    series = [
        ForecastPoint("2026-08-25T14:00:00Z", 41.0),
        ForecastPoint("2026-08-25T15:00:00Z", 43.0),
    ]
    assert nearest_forecast(series, "2026-08-25T15:00:00Z").temperature_c == 43.0
    assert nearest_forecast(series, "2026-08-25T14:30:00Z").temperature_c == 41.0


def test_recommend_ranks_lowest_canopy_first_when_beta_negative():
    coef = Coefficients(intercept=0, canopy=-8.0, asphalt=4.0, sky=1.0, building=2.0, target_canopy_frac=0.4)
    hot = _segment(image="hot", canopy=0.05, delta=5.0)
    cool = _segment(image="cool", canopy=0.35, delta=-1.0)
    ranked = rank_interventions([cool, hot], coef, limit=2)
    assert ranked[0].image_id == "hot"
    assert ranked[0].estimated_cooling_c > ranked[1].estimated_cooling_c
    assert abs(estimated_delta_t(0.05, 0.4, -8.0) - (-8.0 * 0.35)) < 1e-9


def test_grid_spacing_is_about_50m():
    city = get_city("phoenix")
    points = grid_centroids(city.bbox, GRID_SPACING_M)
    assert 200 < len(points) < 8000
    same_lat = [p for p in points if p[0] == points[0][0]]
    assert len(same_lat) >= 2
    _, d_lon = metres_to_degrees(points[0][0], GRID_SPACING_M)
    assert abs((same_lat[1][1] - same_lat[0][1]) - d_lon) < 1e-5


def test_block_id_stable():
    assert block_id(33.45, -112.07) == block_id(33.45, -112.07)
    assert block_id(33.45, -112.07) != block_id(34.45, -112.07)


def test_metrics():
    truth = [0.0, 1.0, 2.0, 3.0, 10.0]
    pred = [0.1, 1.1, 1.9, 3.2, 9.0]
    assert mae(truth, pred) < 0.5
    assert r_squared(truth, pred) > 0.9
    assert spearman_rho(truth, pred) > 0.9
    assert 0.0 <= top_decile_precision(truth, pred) <= 1.0


def test_linear_b1():
    model = LinearFeatureRegressor(
        Coefficients(intercept=1.0, canopy=-4.0, asphalt=2.0, sky=0.5, building=1.0)
    )
    features = UrbanFormFeatures(canopy_frac=0.5, asphalt_frac=0.2, sky_frac=0.2, building_frac=0.1)
    # 1 - 2 + 0.4 + 0.1 + 0.1 = -0.4
    assert abs(model.predict_delta_t(features) - (-0.4)) < 1e-9


def test_leakage_detected_on_shared_block():
    rows = [
        _segment(block="same", split="train", image="a"),
        _segment(block="same", split="test", image="b"),
    ]
    report = leakage_report(rows)
    assert report["ok"] is False
    assert "same" in report["leaked_blocks"]


def test_holdout_city_cannot_be_in_train():
    rows = [_segment(city="miami", split="train", image="m1")]
    assert leakage_report(rows)["ok"] is False


def test_rejects_panorama_and_night():
    city = get_city("phoenix")
    now = datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc)
    pano = {
        "is_pano": True,
        "captured_at": now.timestamp() * 1000,
        "geometry": {"coordinates": [-112.07, 33.45]},
        "camera_type": "perspective",
        "quality_score": 0.9,
    }
    ok, reason = is_usable_image(pano, city, now=now)
    assert ok is False
    assert reason == "panorama"

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from heatlens.config import Settings
from heatlens.domain.cities import BoundingBox, City, get_city
from heatlens.store import LABEL_COLUMNS
from ingest.fortyguard import HEATMAP_DATE_LAG_DAYS, default_heatmap_date, delta_t_for_point, fetch_city_heatmap
from ingest.imagery import download_city_photos
from heatlens.ingest.build import _assign_split, _backfill_delta_t


def _tiny_phoenix():
    # 40m box: smaller than the 50m grid spacing, so exactly one grid point falls
    # inside it (see heatlens/ingest/grid.py's centroid stepping).
    from heatlens.domain.cities import downtown_bbox

    bbox = downtown_bbox(33.4484, -112.0740, half_km=0.02)
    return City("phoenix", "Phoenix", "train", bbox, "America/Phoenix", True, (33.4484, -112.0740))



def _daylight_capture_iso(city: City):
    local = datetime.now(ZoneInfo(city.timezone)).replace(hour=14, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def test_download_city_photos_accepts_good_image_and_skips_second_hit(tmp_path):
    city = _tiny_phoenix()
    image = {
        "id": "img-1",
        "geometry": {"type": "Point", "coordinates": [-112.0740, 33.4484]},
        "computed_geometry": {"type": "Point", "coordinates": [-112.0740, 33.4484]},
        "captured_at": _daylight_capture_iso(city),
        "compass_angle": 90.0,
        "camera_type": "perspective",
        "is_pano": False,
        "quality_score": 0.9,
        "thumb_1024_url": "https://images.mapillary.com/thumb/img-1.jpg",
    }

    def mapillary_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/images"
        return httpx.Response(200, json={"data": [image]})

    def download_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"fake-jpeg-bytes")

    from heatlens.clients.mapillary import MapillaryClient

    mapillary = MapillaryClient("test-token", transport=httpx.MockTransport(mapillary_handler))
    downloader = httpx.Client(transport=httpx.MockTransport(download_handler))
    out_dir = tmp_path / "raw" / city.id

    try:
        results = list(
            download_city_photos(city, mapillary, out_dir, spacing_m=50.0, downloader=downloader)
        )
    finally:
        mapillary.close()
        downloader.close()

    assert len(results) == 1
    result = results[0]
    assert result.accepted is True
    assert result.reason == "ok"
    assert result.photo_path == out_dir / "img-1.jpg"
    assert result.photo_path.read_bytes() == b"fake-jpeg-bytes"


def test_download_city_photos_rejects_pano():
    city = _tiny_phoenix()
    image = {
        "id": "img-2",
        "geometry": {"type": "Point", "coordinates": [-112.0740, 33.4484]},
        "captured_at": _daylight_capture_iso(city),
        "camera_type": "perspective",
        "is_pano": True,
        "quality_score": 0.9,
        "thumb_1024_url": "https://images.mapillary.com/thumb/img-2.jpg",
    }

    def mapillary_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [image]})

    from heatlens.clients.mapillary import MapillaryClient

    mapillary = MapillaryClient("test-token", transport=httpx.MockTransport(mapillary_handler))
    try:
        results = list(download_city_photos(city, mapillary, __import__("pathlib").Path("/tmp/unused-heatlens-test")))
    finally:
        mapillary.close()

    assert len(results) == 1
    assert results[0].accepted is False
    assert results[0].reason == "panorama"


def test_delta_t_for_point_picks_nearest_tile():
    result = {
        "stats_data": {"Temperature_stats": {"Mean": 40.0}},
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [-112.0740, 33.4484]},
                "properties": {"temperature": 43.5},
            },
            {
                "geometry": {"type": "Point", "coordinates": [-112.2000, 33.6000]},
                "properties": {"temperature": 20.0},
            },
        ],
    }
    delta = delta_t_for_point(result, city_mean_c=40.0, lat=33.4484, lon=-112.0740)
    assert delta == 3.5


def test_delta_t_for_point_reads_real_map_data_shape():
    """Real FortyGuard shape confirmed 2026-08-28: tiles live under
    map_data.features, and each tile's temperature is `average_temperature`
    directly on properties -- not the originally-guessed shapes."""
    result = {
        "map_data": {
            "type": "FeatureCollection",
            "features": [
                {
                    "id": "0",
                    "properties": {"tile_id": 0, "average_temperature": 34.9592},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-84.4040, 33.7358],
                                [-84.4029, 33.7358],
                                [-84.4029, 33.7367],
                                [-84.4040, 33.7367],
                                [-84.4040, 33.7358],
                            ]
                        ],
                    },
                },
                {
                    "id": "1",
                    "properties": {"tile_id": 1, "average_temperature": 20.0},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-84.6000, 33.9000],
                                [-84.5990, 33.9000],
                                [-84.5990, 33.9010],
                                [-84.6000, 33.9010],
                                [-84.6000, 33.9000],
                            ]
                        ],
                    },
                },
            ],
        },
        "stats_data": {"activity_id": "act-real", "n_cells": 2},
    }
    delta = delta_t_for_point(result, city_mean_c=30.0, lat=33.7362, lon=-84.4034)
    assert delta == round(34.9592 - 30.0, 2)


def test_fetch_city_heatmap_falls_back_to_tile_mean_when_stats_data_has_no_mean():
    """stats_data has only ever been observed as {activity_id, n_cells} --
    no confirmed city-mean field. fetch_city_heatmap should compute the mean
    from the real tile temperatures instead of raising."""
    city = get_city("atlanta")
    payload_result = {
        "map_data": {
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {"average_temperature": 30.0},
                    "geometry": {"type": "Point", "coordinates": [-84.388, 33.749]},
                },
                {
                    "properties": {"average_temperature": 40.0},
                    "geometry": {"type": "Point", "coordinates": [-84.389, 33.750]},
                },
            ],
        },
        "stats_data": {"activity_id": "act-real", "n_cells": 2},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/heatmap":
            return httpx.Response(200, json={"error": False, "data": {"activity_id": "act-real"}})
        if request.url.path == "/v1/status/act-real":
            return httpx.Response(
                200, json={"error": False, "data": {"status": "Completed", "result": payload_result}}
            )
        return httpx.Response(404, json={"error": True})

    from heatlens.clients.fortyguard import FortyGuardClient

    client = FortyGuardClient("test-key", "https://api.fortyguard.com", transport=httpx.MockTransport(handler))
    try:
        result, city_mean = fetch_city_heatmap(city, client, start_date="2026-08-20", start_time="14:00")
    finally:
        client.close()
    assert city_mean == 35.0  # mean of 30.0 and 40.0 -- real observed tile data, not invented


def test_default_heatmap_date_has_safe_lag():
    """'Today' reliably returns n_cells: 0 (confirmed 2026-08-28) -- the
    default query date must be lagged, not today."""
    expected = (datetime.now(timezone.utc).date() - timedelta(days=HEATMAP_DATE_LAG_DAYS)).isoformat()
    assert default_heatmap_date() == expected
    assert default_heatmap_date() != datetime.now(timezone.utc).date().isoformat()


def test_assign_split_holdout_city_always_holdout():
    miami = get_city("miami")
    assert _assign_split(miami, "b_1_1") == "holdout_city"
    assert _assign_split(miami, "b_99_99") == "holdout_city"


def test_assign_split_is_deterministic_per_block():
    phoenix = get_city("phoenix")
    first = _assign_split(phoenix, "b_14_22")
    second = _assign_split(phoenix, "b_14_22")
    assert first == second
    assert first in ("train", "test")


def test_backfill_delta_t_force_overwrites_only_target_city_and_records_query_date(tmp_path, monkeypatch):
    """--force lets us re-test a city (e.g. Atlanta on a different date)
    without touching another city's already-good rows, and the actual
    FortyGuard query date must land in the CSV (Moneeb's requirement)."""
    import csv
    import ingest.fortyguard as fg_module

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    labels_path = data_dir / "labels.csv"
    fieldnames = list(LABEL_COLUMNS) + ["source", "validated"]
    rows = [
        {"image_id": "atl-1", "lat": "33.75", "lon": "-84.39", "city": "atlanta", "delta_t": "0.01", "t_ref_window": "14:00"},
        {"image_id": "chi-1", "lat": "41.88", "lon": "-87.63", "city": "chicago", "delta_t": "0.5", "t_ref_window": "14:00"},
    ]
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    def fake_fetch(city, client, **kwargs):
        assert kwargs["start_date"] == "2024-07-15"
        assert kwargs["start_time"] == "14:00"
        assert kwargs["granularity"] == 60
        return {"fake": True}, 30.0

    def fake_delta(result, city_mean, lat, lon):
        return 5.0

    monkeypatch.setattr(fg_module, "fetch_city_heatmap", fake_fetch)
    monkeypatch.setattr(fg_module, "delta_t_for_point", fake_delta)

    settings = Settings({
        "HEATLENS_LABELS_PATH": str(labels_path),
        "HEATLENS_CACHE_PATH": str(tmp_path / "cache.sqlite"),
        "FORTYGUARD_API_KEY_ATLANTA": "ga-key",
    })

    rc = _backfill_delta_t(
        [get_city("atlanta")],
        settings,
        heatmap_date="2024-07-15",
        heatmap_time="14:00",
        granularity=60,
        force=True,
    )
    assert rc == 0

    with labels_path.open(newline="", encoding="utf-8") as handle:
        result_rows = {r["image_id"]: r for r in csv.DictReader(handle)}

    assert result_rows["atl-1"]["delta_t"] == "5.0"
    assert result_rows["atl-1"]["fg_query_date"] == "2024-07-15"
    # chicago row must be completely untouched -- --force with --city atlanta
    # must never overwrite another city's already-good data.
    assert result_rows["chi-1"]["delta_t"] == "0.5"
    assert result_rows["chi-1"].get("fg_query_date", "") == ""

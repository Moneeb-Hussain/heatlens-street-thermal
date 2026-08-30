from pathlib import Path

from heatlens.ml.pool import merge_label_rows, write_filled_labels


def _write_csv(path: Path, rows):
    import csv

    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_zero_canopy_counts_as_filled():
    from heatlens.ml.segment import _has_fractions

    assert _has_fractions(
        {
            "canopy_frac": 0.0,
            "asphalt_frac": 0.5,
            "sky_frac": 0.2,
            "building_frac": 0.3,
        }
    )
    assert not _has_fractions(
        {
            "canopy_frac": "",
            "asphalt_frac": 0.5,
            "sky_frac": 0.2,
            "building_frac": 0.3,
        }
    )


def test_merge_keeps_both_cities_and_skips_empty_fractions(tmp_path):
    atlanta = tmp_path / "atl.csv"
    chicago = tmp_path / "chi.csv"
    _write_csv(
        atlanta,
        [
            {
                "image_id": "a1",
                "lat": "33.7",
                "lon": "-84.3",
                "city": "atlanta",
                "delta_t": "0.5",
                "canopy_frac": "0.1",
                "asphalt_frac": "0.4",
                "sky_frac": "0.2",
                "building_frac": "0.3",
                "split": "train",
                "source": "fortyguard",
                "validated": "True",
                "block_id": "b_1",
            }
        ],
    )
    _write_csv(
        chicago,
        [
            {
                "image_id": "c1",
                "lat": "41.8",
                "lon": "-87.6",
                "city": "chicago",
                "delta_t": "0.2",
                "canopy_frac": "",
                "asphalt_frac": "",
                "sky_frac": "",
                "building_frac": "",
                "split": "train",
                "source": "fortyguard",
                "validated": "True",
                "block_id": "b_2",
            },
            {
                "image_id": "c2",
                "lat": "41.9",
                "lon": "-87.7",
                "city": "chicago",
                "delta_t": "0.3",
                "canopy_frac": "0.05",
                "asphalt_frac": "0.5",
                "sky_frac": "0.2",
                "building_frac": "0.25",
                "split": "test",
                "source": "fortyguard",
                "validated": "True",
                "block_id": "b_3",
            },
        ],
    )
    fields, rows = merge_label_rows([atlanta, chicago])
    assert {row["image_id"] for row in rows} == {"a1", "c1", "c2"}
    out = tmp_path / "merged.csv"
    filled = write_filled_labels(out, fields, rows)
    assert {row["image_id"] for row in filled} == {"a1", "c2"}
    text = out.read_text(encoding="utf-8")
    assert "atlanta" in text and "chicago" in text
    assert "c1" not in text

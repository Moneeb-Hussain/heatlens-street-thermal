from heatlens.clients.nominatim import (
    intersection_label,
    road_from_address,
    road_from_display_name,
    road_from_nominatim,
    road_from_photon,
)


def test_road_from_address_prefers_road():
    assert road_from_address({"road": "W Van Buren St", "suburb": "Central City"}) == "W Van Buren St"


def test_road_from_display_name_skips_house_number():
    assert (
        road_from_display_name(
            "55, Marietta Street, Five Points, Atlanta, Georgia, United States"
        )
        == "Marietta Street"
    )


def test_road_from_nominatim_uses_display_name_if_no_road():
    assert (
        road_from_nominatim(
            {"display_name": "55, Marietta Street, Atlanta, Georgia, United States"}
        )
        == "Marietta Street"
    )


def test_road_from_photon_uses_highway_name():
    assert (
        road_from_photon(
            {
                "features": [
                    {
                        "properties": {
                            "osm_key": "highway",
                            "type": "street",
                            "name": "Marietta Street",
                        }
                    }
                ]
            }
        )
        == "Marietta Street"
    )


def test_intersection_label_joins_two_roads():
    assert intersection_label(["W Van Buren St", "S 15th Ave"]) == "W Van Buren St & S 15th Ave"


def test_intersection_label_single():
    assert intersection_label(["Peachtree Street"]) == "Peachtree Street"


def test_intersection_label_empty():
    assert intersection_label([]) is None

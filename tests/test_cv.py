from heatlens.domain.types import UrbanFormFeatures
from heatlens.ml.fractions import ADE_BUILDING, ADE_ROAD, ADE_SKY, ADE_TREE, fractions_from_class_ids
from heatlens.ml.linear import LinearFeatureRegressor
from heatlens.ml.ols import fit_delta_t_coefficients


def test_fractions_from_known_mask():
    # 2 canopy, 1 road, 1 sky, 1 building, 1 other → 6 pixels
    mask = [ADE_TREE, ADE_TREE, ADE_ROAD, ADE_SKY, ADE_BUILDING, 0]
    fracs = fractions_from_class_ids(mask)
    assert fracs["canopy_frac"] == 0.3333
    assert fracs["asphalt_frac"] == 0.1667
    assert fracs["sky_frac"] == 0.1667
    assert fracs["building_frac"] == 0.1667


def test_ols_recovers_known_coefficients():
    rows = []
    for i in range(16):
        canopy = 0.04 * (i % 8)
        asphalt = 0.05 * (i % 5)
        sky = 0.03 * (i % 6)
        building = 0.02 * (i % 7)
        delta = 1.0 + (-4.0) * canopy + 2.0 * asphalt + 0.5 * sky + 1.0 * building
        rows.append(
            {
                "canopy_frac": canopy,
                "asphalt_frac": asphalt,
                "sky_frac": sky,
                "building_frac": building,
                "delta_t": delta,
            }
        )
    fitted = fit_delta_t_coefficients(rows)
    assert abs(fitted.intercept - 1.0) < 0.05
    assert abs(fitted.canopy - (-4.0)) < 0.05
    assert abs(fitted.asphalt - 2.0) < 0.05
    model = LinearFeatureRegressor(fitted)
    pred = model.predict_delta_t(
        UrbanFormFeatures(canopy_frac=0.2, asphalt_frac=0.3, sky_frac=0.2, building_frac=0.15)
    )
    expected = 1.0 - 4.0 * 0.2 + 2.0 * 0.3 + 0.5 * 0.2 + 1.0 * 0.15
    assert abs(pred - expected) < 0.05


def test_positive_canopy_is_clipped_to_zero():
    rows = []
    for i in range(16):
        canopy = 0.04 * (i % 8)
        asphalt = 0.05 * (i % 5)
        delta = 2.0 + 3.0 * canopy + 1.0 * asphalt
        rows.append(
            {
                "canopy_frac": canopy,
                "asphalt_frac": asphalt,
                "sky_frac": 0.1,
                "building_frac": 0.1,
                "delta_t": delta,
            }
        )
    fitted = fit_delta_t_coefficients(rows)
    assert fitted.canopy <= 0.0

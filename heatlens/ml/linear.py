"""B1 linear model: delta_t from urban-form fractions. Coefficients come from a file."""

from __future__ import annotations

from heatlens.domain.types import Coefficients, UrbanFormFeatures


class LinearFeatureRegressor(object):
    name = "linear_features_b1"

    def __init__(self, coefficients: Coefficients):
        self.coefficients = coefficients

    def predict_delta_t(self, features: UrbanFormFeatures) -> float:
        c = self.coefficients
        return (
            c.intercept
            + c.canopy * features.canopy_frac
            + c.asphalt * features.asphalt_frac
            + c.sky * features.sky_frac
            + c.building * features.building_frac
        )

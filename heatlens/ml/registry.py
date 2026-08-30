from __future__ import annotations

from typing import Optional

from heatlens.config import Settings
from heatlens.errors import CapabilityUnavailable
from heatlens.ml.linear import LinearFeatureRegressor
from heatlens.store import load_coefficients


def load_linear_regressor(settings: Settings) -> LinearFeatureRegressor:
    return LinearFeatureRegressor(load_coefficients(settings.coefficients_path))


def load_onnx_regressor(settings: Settings):
    if not settings.has_model():
        raise CapabilityUnavailable(
            "MODEL_NOT_AVAILABLE",
            "No ONNX artefact at {0}. Train before calling vision inference.".format(settings.model_path),
        )
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise CapabilityUnavailable(
            "MODEL_NOT_AVAILABLE",
            "ONNX file present but onnxruntime is not installed. "
            "It has no Python 3.14 wheel — skip ONNX on this venv, or use 3.11/3.12.",
        ) from exc
    session = ort.InferenceSession(str(settings.model_path), providers=["CPUExecutionProvider"])
    return OnnxRegressor(session)


class OnnxRegressor(object):
    name = "onnx_vision"

    def __init__(self, session):
        self._session = session

    def predict_from_chw(self, chw_float32):
        inputs = self._session.get_inputs()
        if not inputs:
            raise CapabilityUnavailable("MODEL_NOT_AVAILABLE", "ONNX model has no inputs")
        name = inputs[0].name
        outputs = self._session.run(None, {name: chw_float32})
        return float(outputs[0].reshape(-1)[0])


def available_model_name(settings: Settings) -> Optional[str]:
    if settings.has_model():
        return "onnx_vision"
    if settings.has_coefficients():
        return "linear_features_b1"
    return None

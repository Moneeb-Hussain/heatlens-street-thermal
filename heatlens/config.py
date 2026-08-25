from __future__ import annotations

import os
from pathlib import Path
from typing import List


class Settings(object):
    def __init__(self, environ=None):
        env = environ if environ is not None else os.environ
        self.data_dir = Path(env.get("HEATLENS_DATA_DIR", "data"))
        self.segments_path = Path(env.get("HEATLENS_SEGMENTS_PATH", "data/segments.json"))
        self.labels_path = Path(env.get("HEATLENS_LABELS_PATH", "data/labels.csv"))
        self.coefficients_path = Path(env.get("HEATLENS_COEFFICIENTS_PATH", "data/coefficients.json"))
        self.model_path = Path(env.get("HEATLENS_MODEL_PATH", "data/models/regressor.onnx"))
        self.cache_path = Path(env.get("HEATLENS_CACHE_PATH", "data/cache/heatlens.sqlite"))
        self.allowed_origins = env.get("HEATLENS_ALLOWED_ORIGINS", "http://localhost:3000")
        self.max_upload_bytes = _int_from(env, "HEATLENS_MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
        self.fortyguard_api_key = (env.get("FORTYGUARD_API_KEY") or "").strip() or None
        self.fortyguard_base_url = (
            env.get("FORTYGUARD_BASE_URL") or "https://api.fortyguard.com"
        ).rstrip("/")
        self.mapillary_access_token = (env.get("MAPILLARY_ACCESS_TOKEN") or "").strip() or None

    def origins(self) -> List[str]:
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]

    def has_fortyguard(self) -> bool:
        return self.fortyguard_api_key is not None

    def has_mapillary(self) -> bool:
        return self.mapillary_access_token is not None

    def has_segments(self) -> bool:
        return self.segments_path.is_file()

    def has_coefficients(self) -> bool:
        return self.coefficients_path.is_file()

    def has_model(self) -> bool:
        return self.model_path.is_file()


def _int_from(env, name, default):
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError("{0} must be an integer, got {1!r}".format(name, raw))


def load_settings() -> Settings:
    _load_dotenv()
    return Settings()


def _load_dotenv():
    """Minimal .env loader. Does not override existing process env."""
    path = Path(".env")
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

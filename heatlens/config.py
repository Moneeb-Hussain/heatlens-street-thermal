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
        self._env = env  # kept for per-city FortyGuard key lookups below

    def origins(self) -> List[str]:
        parts = [part.strip() for part in self.allowed_origins.split(",") if part.strip()]
        if "*" in parts:
            return ["*"]
        return parts

    def has_fortyguard(self) -> bool:
        if self.fortyguard_api_key is not None:
            return True
        from heatlens.domain.cities import CITIES

        return any(self.has_fortyguard_for(city.id) for city in CITIES)

    def fortyguard_api_key_for(self, city_id):
        """FortyGuard locks one account to one US state, chosen at signup and
        not changeable (confirmed by their support 2026-08-27). Atlanta/GA,
        Chicago/IL, Miami/FL each need their OWN account+key. Set
        FORTYGUARD_API_KEY_<CITY_ID> (e.g. FORTYGUARD_API_KEY_ATLANTA) in .env
        for each city; falls back to the shared FORTYGUARD_API_KEY if no
        per-city key is set (fine for single-state setups).
        """
        specific = (self._env.get("FORTYGUARD_API_KEY_{0}".format(city_id.upper())) or "").strip()
        return specific or self.fortyguard_api_key

    def has_fortyguard_for(self, city_id) -> bool:
        return self.fortyguard_api_key_for(city_id) is not None

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

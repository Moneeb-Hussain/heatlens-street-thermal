from __future__ import annotations

from functools import lru_cache
from typing import Optional

from heatlens.clients.cache import ResponseCache
from heatlens.clients.fortyguard import FortyGuardClient
from heatlens.clients.nominatim import NominatimClient
from heatlens.config import Settings, load_settings
from heatlens.ml.registry import available_model_name, load_linear_regressor
from heatlens.store import JsonSegmentStore, load_coefficients


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_store() -> JsonSegmentStore:
    return JsonSegmentStore(get_settings().segments_path)


@lru_cache(maxsize=1)
def get_cache() -> ResponseCache:
    return ResponseCache(get_settings().cache_path)


def get_fortyguard(city_id=None) -> FortyGuardClient:
    settings = get_settings()
    api_key = settings.fortyguard_api_key_for(city_id) if city_id else settings.fortyguard_api_key
    return FortyGuardClient(
        api_key=api_key,
        base_url=settings.fortyguard_base_url,
        cache=get_cache(),
    )


def get_nominatim() -> NominatimClient:
    return NominatimClient(cache=get_cache())


def try_coefficients():
    return load_coefficients(get_settings().coefficients_path)


def try_linear():
    return load_linear_regressor(get_settings())


def model_capability() -> Optional[str]:
    return available_model_name(get_settings())

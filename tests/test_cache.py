from concurrent.futures import ThreadPoolExecutor

from heatlens.clients.cache import ResponseCache, cache_key


def test_cache_readable_from_another_thread(tmp_path):
    cache = ResponseCache(tmp_path / "heatlens.sqlite")
    key = cache_key("heatmap", {"city": "atlanta"})
    cache.put(key, {"mean": 34.4})

    def read():
        return cache.get(key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in (pool.submit(read), pool.submit(read))]
    assert results == [{"mean": 34.4}, {"mean": 34.4}]
    cache.close()

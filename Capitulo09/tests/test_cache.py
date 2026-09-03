import asyncio
from app.service import MemoryProducts, ProductService, prepare_demo_cache

def run(value): return asyncio.run(value)

class FakeCache:
    def __init__(self): self.rows, self.ttls, self.fail = {}, {}, False
    async def get(self, key):
        if self.fail: raise ConnectionError("redis unavailable")
        if self.ttls.get(key, 0) <= 0: self.rows.pop(key, None)
        return self.rows.get(key)
    async def set(self, key, value, ttl):
        if self.fail: raise ConnectionError("redis unavailable")
        self.rows[key], self.ttls[key] = value.copy(), ttl
    async def delete(self, key):
        if self.fail: raise ConnectionError("redis unavailable")
        self.rows.pop(key, None)

def test_miss_fills_cache():
    repo, cache = MemoryProducts(), FakeCache(); service = ProductService(repo, cache)
    assert run(service.get_product("p-1"))["stock"] == 8
    assert service.key("p-1") in cache.rows and repo.reads == 1

def test_hit_avoids_second_repository_read():
    repo, cache = MemoryProducts(), FakeCache(); service = ProductService(repo, cache)
    run(service.get_product("p-1")); run(service.get_product("p-1"))
    assert repo.reads == 1

def test_expired_entry_becomes_miss():
    repo, cache = MemoryProducts(), FakeCache(); service = ProductService(repo, cache)
    run(service.get_product("p-1")); cache.ttls[service.key("p-1")] = 0
    run(service.get_product("p-1")); assert repo.reads == 2

def test_update_invalidates_cached_value():
    repo, cache = MemoryProducts(), FakeCache(); service = ProductService(repo, cache)
    run(service.get_product("p-1")); run(service.update_product("p-1", {"stock": 7}))
    assert service.key("p-1") not in cache.rows
    assert run(service.get_product("p-1"))["stock"] == 7

def test_cache_failure_falls_back_to_repository():
    repo, cache, events = MemoryProducts(), FakeCache(), []
    cache.fail = True; service = ProductService(repo, cache, events.append)
    assert run(service.get_product("p-1"))["name"] == "Keyboard"
    assert repo.reads == 1 and "BYPASS" in events

def test_demo_preparation_tolerates_cache_failure():
    cache, events = FakeCache(), []
    cache.fail = True
    run(prepare_demo_cache(cache, "catalog:product:p-1:v1", events.append))
    assert events == ["BYPASS-PREP"]

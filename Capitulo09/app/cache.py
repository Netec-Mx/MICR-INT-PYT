import json
from typing import Any, Protocol

class Cache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...
    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...

class RedisCache:
    def __init__(self, client): self.client = client
    async def get(self, key):
        raw = await self.client.get(key)
        return None if raw is None else json.loads(raw)
    async def set(self, key, value, ttl):
        await self.client.set(key, json.dumps(value, ensure_ascii=False, separators=(",", ":")), ex=ttl)
    async def delete(self, key): await self.client.delete(key)

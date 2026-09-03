import asyncio, os
from redis.asyncio import Redis
from app.cache import RedisCache
from app.service import MemoryProducts, ProductService, prepare_demo_cache

async def main():
    client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True, socket_connect_timeout=1)
    service = ProductService(MemoryProducts(), RedisCache(client), print)
    try:
        await prepare_demo_cache(service.cache, service.key("p-1"), print)
        print(await service.get_product("p-1")); print(await service.get_product("p-1"))
        await service.update_product("p-1", {"stock": 7}); print(await service.get_product("p-1"))
    finally: await client.aclose()

if __name__ == "__main__": asyncio.run(main())

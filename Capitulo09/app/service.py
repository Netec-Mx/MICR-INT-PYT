from copy import deepcopy

class ProductNotFound(Exception): pass

async def prepare_demo_cache(cache, key, observer=lambda event: None):
    try:
        await cache.delete(key)
    except Exception:
        observer("BYPASS-PREP")

class MemoryProducts:
    def __init__(self):
        self.rows = {"p-1": {"id": "p-1", "name": "Keyboard", "stock": 8}}
        self.reads = 0
    async def get(self, product_id): self.reads += 1; return deepcopy(self.rows.get(product_id))
    async def update(self, product_id, changes): self.rows[product_id].update(changes); return deepcopy(self.rows[product_id])

class ProductService:
    TTL_SECONDS = 60
    def __init__(self, repository, cache, observer=lambda event: None):
        self.repository, self.cache, self.observer = repository, cache, observer
    @staticmethod
    def key(product_id): return f"catalog:product:{product_id}:v1"
    async def get_product(self, product_id):
        key = self.key(product_id)
        try:
            cached = await self.cache.get(key)
            if cached is not None: self.observer("HIT"); return cached
        except Exception: self.observer("BYPASS")
        self.observer("MISS")
        product = await self.repository.get(product_id)
        if product is None: raise ProductNotFound(product_id)
        try: await self.cache.set(key, product, self.TTL_SECONDS)
        except Exception: self.observer("BYPASS")
        return product
    async def update_product(self, product_id, changes):
        product = await self.repository.update(product_id, changes)  # LAB 1: confirmar fuente
        try: await self.cache.delete(self.key(product_id))  # LAB 2: invalidar después
        except Exception: self.observer("BYPASS")
        else: self.observer("INVALIDATE")
        return product

import asyncio
from decimal import Decimal
import pytest
from app.schemas import ProductInput
from app.service import CatalogService, CompensationFailed

class MemorySql:
    def __init__(self, fail_delete=False): self.rows, self.fail_delete = {}, fail_delete
    async def add(self, data):
        row = {"id": "p-1", "sku": data.sku, "name": data.name, "price": data.price, "stock": data.stock}; self.rows["p-1"] = row; return row
    async def get(self, product_id): return self.rows.get(product_id)
    async def delete(self, product_id):
        if self.fail_delete: raise RuntimeError("postgres unavailable")
        self.rows.pop(product_id, None)

class MemoryDocuments:
    def __init__(self, fail_add=False): self.rows, self.fail_add = {}, fail_add
    async def add(self, product_id, data):
        if self.fail_add: raise RuntimeError("mongo unavailable")
        self.rows[product_id] = {"description": data.description, "attributes": data.attributes, "tags": data.tags}
    async def get(self, product_id): return self.rows.get(product_id)

@pytest.fixture
def product(): return ProductInput("SKU-1", "Keyboard", Decimal("49.90"), 8, "Mechanical", {"layout": "ES"}, ["input"])

def run(awaitable): return asyncio.run(awaitable)

def test_success_combines_both_stores(product):
    result = run(CatalogService(MemorySql(), MemoryDocuments()).create(product))
    assert result.id == "p-1" and result.attributes == {"layout": "ES"}

def test_read_combines_existing_data(product):
    service = CatalogService(MemorySql(), MemoryDocuments()); run(service.create(product))
    assert run(service.get("p-1")).description == "Mechanical"

def test_document_failure_compensates_sql(product):
    sql = MemorySql()
    with pytest.raises(RuntimeError, match="mongo unavailable"): run(CatalogService(sql, MemoryDocuments(True)).create(product))
    assert sql.rows == {}

def test_double_failure_is_reported(product):
    sql = MemorySql(True)
    with pytest.raises(CompensationFailed, match="fallo de compensación"): run(CatalogService(sql, MemoryDocuments(True)).create(product))
    assert "p-1" in sql.rows

def test_document_keeps_sku_for_reproducible_cleanup(product):
    from app.schemas import detail_document
    document = detail_document("p-1", product)
    assert document["sku"] == "SKU-1"
    assert document["product_id"] == "p-1"

from typing import Any
from app.schemas import ProductInput, ProductView

class ProductNotFound(Exception): pass
class CompensationFailed(Exception): pass

class CatalogService:
    def __init__(self, sql: Any, documents: Any):
        self.sql, self.documents = sql, documents

    async def create(self, data: ProductInput) -> ProductView:
        product = await self.sql.add(data)  # LAB 1: commit SQL
        try:
            await self.documents.add(product["id"], data)  # LAB 2: transacción Mongo
        except Exception as document_error:
            try:
                await self.sql.delete(product["id"])  # LAB 3: compensación idempotente
            except Exception as compensation_error:
                raise CompensationFailed(f"Fallo documental: {document_error}; fallo de compensación: {compensation_error}") from compensation_error
            raise
        return await self.get(product["id"])

    async def get(self, product_id: str) -> ProductView:
        product = await self.sql.get(product_id)
        if product is None:
            raise ProductNotFound(product_id)
        details = await self.documents.get(product_id) or {}
        return ProductView(**product, description=details.get("description", ""), attributes=details.get("attributes", {}), tags=details.get("tags", []))

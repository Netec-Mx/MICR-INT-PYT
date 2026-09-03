import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import Base
from app.repositories import postgres_factory

PG = os.getenv("POSTGRES_URL", "postgresql+asyncpg://catalog:catalog-lab@localhost:5432/catalog")
MONGO = os.getenv("MONGO_URL", "mongodb://catalog:catalog-lab@localhost:27017/?authSource=admin")

async def initialize():
    engine, _ = postgres_factory(PG)
    async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    client = AsyncIOMotorClient(MONGO)
    await client.catalog_details.product_details.create_index("product_id", unique=True)
    client.close()
    print("PostgreSQL y MongoDB preparados")

if __name__ == "__main__": asyncio.run(initialize())

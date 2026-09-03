import ssl
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
uvicorn.run(
    "inventory_service:app",
    app_dir=str(Path(__file__).parent),
    host="0.0.0.0",
    port=8442,
    ssl_keyfile=str(ROOT / "certs/inventory-service.key"),
    ssl_certfile=str(ROOT / "certs/inventory-service.crt"),
    ssl_ca_certs=str(ROOT / "certs/ca.crt"),
    ssl_cert_reqs=ssl.CERT_REQUIRED,
)

from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
uvicorn.run(
    "auth_service:app",
    app_dir=str(Path(__file__).parent),
    host="0.0.0.0",
    port=8441,
    ssl_keyfile=str(ROOT / "certs/auth-service.key"),
    ssl_certfile=str(ROOT / "certs/auth-service.crt"),
)

from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = (ROOT / "certs/jwt-public.pem").read_text(encoding="utf-8")
app = FastAPI(title="Inventory Service")


def decode_token(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization.removeprefix("Bearer ")
    try:
        return jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["RS256"],  # TODO 1: algoritmo permitido.
            issuer="https://auth-service.local",  # TODO 2: emisor esperado.
            audience="inventory-service",  # TODO 3: audiencia esperada.
            options={"require": ["sub", "roles", "iss", "aud", "iat", "exp"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Invalid token") from error


def require_role(role: str):
    def dependency(claims: dict = Depends(decode_token)) -> dict:
        if role not in claims.get("roles", []):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return claims
    return dependency


@app.get("/inventory")
def read_inventory(_: dict = Depends(require_role("admin"))) -> list[dict]:
    return [{"product_id": 1, "stock": 12}]

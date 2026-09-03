from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_KEY = (ROOT / "certs/jwt-private.pem").read_text(encoding="utf-8")
ISSUER = "https://auth-service.local"
AUDIENCE = "inventory-service"
USERS = {
    "admin": {"password": "lab-admin", "roles": ["admin"]},
    "viewer": {"password": "lab-viewer", "roles": ["viewer"]},
}

app = FastAPI(title="Auth Service")


class Credentials(BaseModel):
    username: str
    password: str


@app.post("/token")
def create_token(credentials: Credentials) -> dict[str, str]:
    user = USERS.get(credentials.username)
    if user is None or credentials.password != user["password"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    now = datetime.now(timezone.utc)
    claims = {
        "sub": credentials.username,
        "roles": user["roles"],
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(claims, PRIVATE_KEY, algorithm="RS256")
    return {"access_token": token, "token_type": "bearer"}

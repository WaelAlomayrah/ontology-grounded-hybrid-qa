import hashlib
import hmac
from typing import Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import Settings, get_settings
from app.models.api import LoginRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
Role = Literal["viewer", "labeler", "analyst", "admin"]
ROLE_LEVEL = {"viewer": 0, "labeler": 1, "analyst": 1, "admin": 2}


def _token(username: str, role: Role, secret: str) -> str:
    signature = hmac.new(secret.encode(), f"{username}:{role}".encode(), hashlib.sha256).hexdigest()
    return f"{username}.{role}.{signature}"


def current_user(authorization: str = Header(default=""), settings: Settings = Depends(get_settings)) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ").strip()
    try: username, role, _ = token.split(".", 2)
    except ValueError:
        raise HTTPException(status_code=401, detail="Authentication required") from None
    if role not in ROLE_LEVEL:
        raise HTTPException(status_code=401, detail="Invalid session")
    validated_role = cast(Role, role)
    if not hmac.compare_digest(token, _token(username, validated_role, settings.admin_token)):
        raise HTTPException(status_code=401, detail="Invalid session")
    return {"username": username, "role": validated_role}


def require_role(minimum: Role):
    def dependency(user: dict[str, str] = Depends(current_user)) -> dict[str, str]:
        if ROLE_LEVEL[user["role"]] < ROLE_LEVEL[minimum]: raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dependency


@router.post("/login")
async def login(request: LoginRequest, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    role: Role | None = request.username if request.username in ROLE_LEVEL else "admin" if request.username == "admin" else None  # type: ignore[assignment]
    if role is None or not hmac.compare_digest(request.password, "admin"):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"token": _token(request.username, role, settings.admin_token), "username": request.username, "role": role}


@router.get("/me")
async def me(user: dict[str, str] = Depends(current_user)) -> dict[str, str]: return user

from fastapi import APIRouter, Request

from app.services.auth import list_users_admin, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def admin_users(request: Request):
    require_admin(request)
    return {"users": list_users_admin()}

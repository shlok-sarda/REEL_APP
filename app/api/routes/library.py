from fastapi import APIRouter, Query

from app.schemas import LibraryResponse
from app.services.library import load_library_payload


router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryResponse)
def get_library(user_id: str = Query(default="default")):
    return LibraryResponse(**load_library_payload(user_id))

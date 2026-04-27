from pathlib import Path

from app.config import PROJECT_ROOT


def normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def slugify_user(user_id: str) -> str:
    value = normalize(user_id) or "default"
    chars = []
    for char in value:
        if char.isalnum():
            chars.append(char.lower())
        else:
            chars.append("_")
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "default"


def user_storage_dir(user_id: str) -> Path:
    slug = slugify_user(user_id)
    if slug == "default":
        return PROJECT_ROOT / "Shlok_reels"
    return PROJECT_ROOT / "user_libraries" / f"{slug}_reels"

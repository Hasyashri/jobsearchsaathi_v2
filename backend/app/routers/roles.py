"""
routers/roles.py — GET /roles and GET /roles/{role_id}
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.schemas import RoleItem, RolesResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/roles", tags=["Roles"])


def _load_roles() -> dict:
    path = settings.DATA_DIR / "role_templates.json"
    if not path.exists():
        raise HTTPException(500, detail="role_templates.json not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("", response_model=RolesResponse, summary="List all available roles")
def list_roles():
    """Return all role IDs and titles from the catalog."""
    roles = _load_roles()
    items = [
        RoleItem(
            role_id=rid,
            title=r.get("title", rid),
            category=r.get("category", ""),
            seniority=r.get("seniority", ""),
            description=r.get("description", ""),
        )
        for rid, r in roles.items()
    ]
    return RolesResponse(roles=items, total=len(items))


@router.get("/{role_id}", response_model=RoleItem, summary="Get a single role")
def get_role(role_id: str):
    roles = _load_roles()
    r = roles.get(role_id)
    if r is None:
        raise HTTPException(404, detail=f"Role '{role_id}' not found.")
    return RoleItem(
        role_id=role_id,
        title=r.get("title", role_id),
        category=r.get("category", ""),
        seniority=r.get("seniority", ""),
        description=r.get("description", ""),
    )

from fastapi import APIRouter, Depends, Request

from app.api.responses import PlaybookPage, PolicyView
from app.contracts import Playbook
from app.errors import ServiceError
from app.security.auth import principal, require
from app.soar.playbooks.engine import catalog
from app.soar.proposals.policy import TargetPolicy

router = APIRouter(tags=["Playbooks and policy"])


@router.get("/v1/playbooks", response_model=PlaybookPage)
def listing(request: Request, p=Depends(principal)):
    return {"items": [b.model_dump(mode="json") for b in catalog(request.app.state.settings.playbook_dir).values()]}


@router.get("/v1/playbooks/{playbook_id}", response_model=Playbook)
def detail(playbook_id: str, request: Request, p=Depends(principal)):
    book = catalog(request.app.state.settings.playbook_dir).get(playbook_id)
    if not book:
        raise ServiceError("playbook_not_found", 404)
    return book


@router.get("/v1/policy", response_model=PolicyView)
def policy(request: Request, p=Depends(require("admin"))):
    policy = TargetPolicy(request.app.state.settings)
    return {
        "protected_assets": sorted(policy.names),
        "protected_roles": sorted(policy.roles),
        "protected_networks": [str(n) for n in policy.networks],
        "lab_asset_ids": sorted(policy.lab_assets),
        "managed_by": "admin-controlled config/policy.yml and environment",
    }

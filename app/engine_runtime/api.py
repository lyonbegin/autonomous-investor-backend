"""Authenticated management of existing native engine smoke workers."""
from fastapi import APIRouter, Depends

from app.core.auth import require_auth
from app.engine_runtime.supervisor import supervisor

router = APIRouter(prefix="/api/v1/ops/engines", tags=["Native engine supervision"],
                   dependencies=[Depends(require_auth)])


@router.get("")
def inventory() -> dict:
    return supervisor.inventory()


@router.get("/{key}")
def status(key: str) -> dict:
    return supervisor.snapshot(key)


@router.post("/{key}/start", status_code=202)
def start(key: str) -> dict:
    return supervisor.start(key)


@router.post("/{key}/stop")
def stop(key: str) -> dict:
    return supervisor.stop(key)


@router.post("/{key}/verify")
def verify(key: str) -> dict:
    return supervisor.demo(key)

from fastapi import APIRouter, Query, status

from app.clients.dependencies import ClientServiceDep
from app.clients.schemas import ClientCreate, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(data: ClientCreate, service: ClientServiceDep) -> ClientRead:
    client = await service.create_client(data)
    return ClientRead.model_validate(client)


@router.get("", response_model=list[ClientRead])
async def list_clients(
    service: ClientServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
) -> list[ClientRead]:
    clients = await service.list_clients(skip=skip, limit=limit, search=search)
    return [ClientRead.model_validate(c) for c in clients]


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(client_id: int, service: ClientServiceDep) -> ClientRead:
    client = await service.get_client(client_id)
    return ClientRead.model_validate(client)


@router.patch("/{client_id}", response_model=ClientRead)
async def update_client(client_id: int, data: ClientUpdate, service: ClientServiceDep) -> ClientRead:
    client = await service.update_client(client_id, data)
    return ClientRead.model_validate(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: int, service: ClientServiceDep) -> None:
    await service.delete_client(client_id)

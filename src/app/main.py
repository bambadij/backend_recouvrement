from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.bootstrap import bootstrap_super_admin
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.exceptions import AppException, app_exception_handler
from app.creances import models as creances_models  # noqa: F401
from app.creances.router import router as creances_router
from app.debiteurs import models as debiteurs_models  # noqa: F401
from app.debiteurs.router import router as debiteurs_router
from app.imports.router import router as imports_router
from app.organisations import models as organisations_models  # noqa: F401
from app.organisations.router import router as organisations_router
from app.paiements import models as paiements_models  # noqa: F401
from app.paiements.router import router as paiements_router
from app.promesses import models as promesses_models  # noqa: F401
from app.promesses.router import router as promesses_router
from app.relances import models as relances_models  # noqa: F401
from app.relances.router import router as relances_router
from app.segmentation import models as segmentation_models  # noqa: F401
from app.segmentation.router import router as segmentation_router
from app.users import models as users_models  # noqa: F401
from app.users.router import auth_router, router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Provisoire : cree les tables au demarrage. A remplacer par Alembic
    # (uv run alembic upgrade head) une fois le schema stabilise.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await bootstrap_super_admin(session)

    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(organisations_router)
app.include_router(debiteurs_router)
app.include_router(creances_router)
app.include_router(paiements_router)
app.include_router(relances_router)
app.include_router(promesses_router)
app.include_router(segmentation_router)
app.include_router(imports_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

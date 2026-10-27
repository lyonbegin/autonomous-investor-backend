from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.demo_routes import router as demo_router
from app.api.routes import router
from app.api.tradingview_routes import router as tradingview_router
from app.alpha_nodes.api import router as alpha_router
from app.alpha_nodes.investment_api import router as investment_router
from app.alpha_nodes.scenario_api import router as scenario_router
from app.alpha_nodes.operations_api import router as operations_router
from app.alpha_nodes.api import require_auth
from app.alpha_nodes.scenario_control_api import router as scenario_control_router
from app.api.source_registry_routes import router as source_registry_router
from app.api.quant_routes import router as quant_router
from app.api.public_routes import router as public_router

app = FastAPI(
    title="Autonomous Investor Backend",
    version=__version__,
    description="Integration API for research, quant R&D, validation, allocation, risk and execution engines.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(demo_router)
# These restored service APIs contain collection and agent mutation operations,
# including GET handlers with side effects. Keep them behind the existing gate.
app.include_router(tradingview_router, dependencies=[Depends(require_auth)])
app.include_router(source_registry_router, dependencies=[Depends(require_auth)])
app.include_router(quant_router, dependencies=[Depends(require_auth)])
app.include_router(public_router)
app.include_router(alpha_router)
app.include_router(investment_router)
app.include_router(scenario_router)
app.include_router(operations_router)
app.include_router(scenario_control_router)

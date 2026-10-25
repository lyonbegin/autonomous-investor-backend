from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.demo_routes import router as demo_router
from app.api.routes import router
from app.api.tradingview_routes import router as tradingview_router
from app.alpha_nodes.api import router as alpha_router
from app.alpha_nodes.investment_api import router as investment_router

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
app.include_router(tradingview_router)
app.include_router(alpha_router)
app.include_router(investment_router)

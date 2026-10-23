from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tradingview_routes import router as tradingview_router
from app.api.source_registry_routes import router as source_registry_router
from app.core.source_registry import init_source_registry_db

app = FastAPI(
    title="Autonomous Investor TradingView Source Service",
    version="0.1.0",
    description="TradingView ideas, community strategies, market scanner and immutable source-to-horizon agent planning.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "autonomous-investor-tradingview"}


init_source_registry_db()

app.include_router(tradingview_router)
app.include_router(source_registry_router)

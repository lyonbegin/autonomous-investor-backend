from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tradingview_routes import router as tradingview_router

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


app.include_router(tradingview_router)

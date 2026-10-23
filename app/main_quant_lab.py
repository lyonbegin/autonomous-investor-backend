from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.quant_routes import router as quant_router
from app.core.quant_lab import init_db
from app.core.macro_data import init_macro_db

app = FastAPI(
    title="Autonomous Investor Quant Lab Control",
    version="0.1.0",
    description="Experiment registry, market-data readiness and validation orchestration for immutable strategy-horizon agents.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    init_macro_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "autonomous-investor-quant-lab-control"}


app.include_router(quant_router)

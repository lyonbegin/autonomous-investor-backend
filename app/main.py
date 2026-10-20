from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router

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

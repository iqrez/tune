import sys
import os

# Add backend/ to sys.path so bare "from core.xxx" imports in api_v1.py resolve
# to backend/core/ (rusefi_connector, parameters, autotune, etc.)
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import api_v1

from contextlib import asynccontextmanager
import threading

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do not block API startup on ECU probing.
    # UI can connect explicitly via /rusefi/connect.
    auto_connect = os.getenv("BASE_TUNE_AUTOCONNECT_ON_START", "0").strip().lower() in ("1", "true", "yes")
    if auto_connect:
        def _bg_connect():
            try:
                from .routers.api_v1 import get_rusefi_client
                client = get_rusefi_client()
                client.connect()
            except Exception as e:
                print(f"Startup connect error: {e}")
        threading.Thread(target=_bg_connect, daemon=True).start()
    yield
    
app = FastAPI(
    title="AI BaseTune Architect Companion Service",
    description="Backend service for deterministic tune generation and AI guardrails for rusEFI.",
    version="1.0.0",
    lifespan=lifespan
)

# Allow React app to communicate with API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1.router)

@app.get("/status")
def get_status():
    return {"status": "ok", "version": "1.0.0"}

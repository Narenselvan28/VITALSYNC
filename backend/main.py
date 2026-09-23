"""
AAROGYA-SHIELD: Edge-AI FastAPI Application Entry Point
Mounts REST API routes, WebSocket endpoint (/ws/live), static dashboard files,
and initializes baseline, database, and machine learning components on startup.
"""

import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api.routes import router as api_router
from backend.api.websocket_manager import ws_manager
from backend.ml.model_registry import get_model_registry
from backend.db.database import get_db
from backend.core.baseline_engine import get_device_baseline

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("  VITALSYNC: Edge-AI Health Monitoring & Early-Warning System")
    print("  Host: Raspberry Pi 4 Edge Target")
    print("  Hardware Nodes: ESP32 (MAX30102, ADXL345, MQ-45, GPS)")
    print("  Status: Initializing models, database, and baselines...")
    print("=" * 60)
    
    # Pre-load ML models
    registry = get_model_registry()
    print(f"[Startup] ML models ready. Active version: {registry.version_info.get('version', '1.0.0-edge')}")
    
    # Pre-connect to MongoDB
    db = get_db()
    
    # Initialize default device baseline
    baseline = get_device_baseline("ESP32-001")
    db.save_baseline(baseline.to_dict())
    
    # Register default device
    db.register_device("ESP32-001", {
        "device_type": "ESP32-Edge-Wearable",
        "sensors": ["MAX30102", "ADXL345", "DHT22", "MQ-45", "NEO-6M GPS"],
        "node_ip": "192.168.1.104",
    })
    print("[Startup] Initialization complete. VITALSYNC Server ready.")
    yield

app = FastAPI(
    title="VITALSYNC Edge-AI API",
    description="Edge-AI personal health monitoring and early-warning system prototype",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local edge and browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST routes
app.include_router(api_router)

# WebSocket live streaming endpoint
@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection open; can receive client pings or direct commands
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Path to frontend directory
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(FRONTEND_DIR):
    # Mount static assets
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    # Serve index.html on root, /test, /monitor, /lab, /alerts, /device
    @app.get("/", include_in_schema=False)
    @app.get("/test", include_in_schema=False)
    @app.get("/monitor", include_in_schema=False)
    @app.get("/lab", include_in_schema=False)
    @app.get("/alerts", include_in_schema=False)
    @app.get("/device", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.routers import fleet, dispatch
from app import seed, simulation
from app.ws_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed.seed_if_empty(db)
        simulation.reoptimize_fleet(db)  # produce an initial plan so the map isn't empty
    finally:
        db.close()
    yield


app = FastAPI(title="Waypoint API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo scope only -- lock this to the deployed frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fleet.router, prefix="/api")
app.include_router(dispatch.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # client doesn't need to send anything; keeps the socket alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

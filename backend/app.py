from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from adapters.juniper.adapter import JuniperAdapter
from core.models import DiscoveryTarget
from database.models import Base
from database.session import SessionLocal, engine
from discovery.jobs import DiscoveryService
from inventory.repository import InventoryRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Infrastructure Vision Platform - Phase 1", lifespan=lifespan)
service = DiscoveryService(JuniperAdapter(), SessionLocal)


def get_session():
    with SessionLocal() as session:
        yield session


@app.post("/api/discovery/jobs")
def create_discovery_job(targets: list[DiscoveryTarget]):
    return service.run(targets)


@app.get("/api/discovery/jobs/{job_id}")
def get_job(job_id: UUID):
    job = service.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Discovery job not found")
    return job


@app.get("/api/devices")
def list_devices(session: Session = Depends(get_session)):
    return [InventoryRepository._device(item) for item in InventoryRepository(session).list()]


@app.get("/api/devices/{device_id}")
def get_device(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    return InventoryRepository._device(record)


@app.get("/api/devices/{device_id}/interfaces")
def get_interfaces(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    return record.interfaces


@app.get("/api/devices/{device_id}/neighbors")
def get_neighbors(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record:
        raise HTTPException(404, "Device not found")
    return record.neighbors


@app.get("/api/devices/{device_id}/health")
def get_health(device_id: str, session: Session = Depends(get_session)):
    record = InventoryRepository(session).get(device_id)
    if not record or not record.health:
        raise HTTPException(404, "Health record not found")
    return record.health


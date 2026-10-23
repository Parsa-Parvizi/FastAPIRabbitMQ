import json
import os
from contextlib import asynccontextmanager

import aio_pika
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.mq import connect_with_retry

from app.db import SessionLocal, TaskRecord, init_db

RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE = os.getenv("QUEUE_NAME", "tasks")


class TaskIn(BaseModel):
    name: str
    payload: dict = {}


async def get_session():
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    connection = await connect_with_retry(RABBIT_URL)
    channel = await connection.channel(publisher_confirms=True)
    await channel.declare_queue(QUEUE, durable=True)
    app.state.connection = connection
    app.state.channel = channel
    yield
    await connection.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health(request: Request):
    return {"rabbitmq": not request.app.state.connection.is_closed}

@app.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    task: TaskIn, request: Request, session: AsyncSession = Depends(get_session)
):
    record = TaskRecord(name=task.name, payload=task.payload)
    session.add(record)
    await session.commit()  # اول DB، بعد صف

    message = aio_pika.Message(
        body=json.dumps({"id": record.id}).encode(),  # فقط id، نه کل داده
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await request.app.state.channel.default_exchange.publish(
        message, routing_key=QUEUE
    )
    return {"id": record.id, "status": record.status}

@app.get("/tasks")
async def list_tasks(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TaskRecord).order_by(TaskRecord.id.desc()).limit(20)
    )
    return [
        {"id": r.id, "name": r.name, "status": r.status}
        for r in result.scalars()
    ]

@app.get("/tasks/{task_id}")
async def get_task(task_id: int, session: AsyncSession = Depends(get_session)):
    record = await session.get(TaskRecord, task_id)
    if record is None:
        raise HTTPException(404, "task not found")
    return {"id": record.id, "name": record.name, "status": record.status}
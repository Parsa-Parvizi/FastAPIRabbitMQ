import asyncio
import json
import os

import aio_pika

from app.db import SessionLocal, TaskRecord, init_db

RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE = os.getenv("QUEUE_NAME", "tasks")


async def handle(message: aio_pika.IncomingMessage):
    async with message.process(requeue=False):
        task_id = json.loads(message.body)["id"]

        async with SessionLocal() as session:
            record = await session.get(TaskRecord, task_id)
            if record is None:
                return  # پیام یتیم؛ ack می‌شه

            try:
                print(f"processing: {record.name} {record.payload}")
                # ... کار اصلی اینجا ...
                record.status = "done"
            except Exception:
                record.status = "failed"
                raise
            finally:
                await session.commit()


async def main():
    await init_db()
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    queue = await channel.declare_queue(QUEUE, durable=True)
    await queue.consume(handle)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
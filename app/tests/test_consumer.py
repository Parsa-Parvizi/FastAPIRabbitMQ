import json

import pytest

from app import consumer
from app.db import SessionLocal, TaskRecord

pytestmark = pytest.mark.usefixtures("db")


class FakeProcess:
    """شبیه message.process(): موفق ← ack، exception ← reject"""

    def __init__(self, msg):
        self.msg = msg

    async def __aenter__(self):
        return self.msg

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            self.msg.rejected = True
        else:
            self.msg.acked = True
        return False  # exception بالا می‌ره، مثل aio_pika واقعی


class FakeMessage:
    def __init__(self, data: dict):
        self.body = json.dumps(data).encode()
        self.acked = False
        self.rejected = False

    def process(self, requeue=False):
        return FakeProcess(self)


async def make_task() -> int:
    async with SessionLocal() as session:
        record = TaskRecord(name="t", payload={})
        session.add(record)
        await session.commit()
        return record.id


async def get_status(task_id: int) -> str:
    async with SessionLocal() as session:
        return (await session.get(TaskRecord, task_id)).status


async def test_successful_message_marks_task_done_and_acks():
    task_id = await make_task()
    msg = FakeMessage({"id": task_id})

    await consumer.handle(msg)

    assert await get_status(task_id) == "done"
    assert msg.acked and not msg.rejected


async def test_message_for_unknown_task_is_acked_and_ignored():
    msg = FakeMessage({"id": 999999})

    await consumer.handle(msg)

    assert msg.acked  # پیام یتیم نباید برای همیشه تو صف بچرخه


async def test_failure_marks_task_failed_and_rejects(monkeypatch):
    task_id = await make_task()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    # handler تو بخش "کار اصلی" فقط print می‌کنه؛ با جایگزین کردنش، شکست رو شبیه‌سازی می‌کنیم
    monkeypatch.setattr(consumer, "print", boom, raising=False)
    msg = FakeMessage({"id": task_id})

    with pytest.raises(RuntimeError):
        await consumer.handle(msg)

    assert await get_status(task_id) == "failed"
    assert msg.rejected and not msg.acked
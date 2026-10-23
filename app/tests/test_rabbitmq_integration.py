import os
import uuid

import aio_pika
import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

URL = os.getenv("RABBITMQ_TEST_URL", "amqp://guest:guest@localhost:5672/")


@pytest_asyncio.fixture
async def channel():
    try:
        conn = await aio_pika.connect(URL, timeout=3)
    except Exception:
        pytest.skip("RabbitMQ is not reachable (docker compose up -d rabbitmq)")
    async with conn:
        yield await conn.channel()


async def drain(queue) -> list[str]:
    out = []
    while (msg := await queue.get(fail=False)) is not None:
        await msg.ack()
        out.append(msg.body.decode())
    return out


async def test_publish_and_consume_roundtrip(channel):
    queue = await channel.declare_queue(f"test.{uuid.uuid4().hex}", exclusive=True)

    await channel.default_exchange.publish(
        aio_pika.Message(body=b"ping"), routing_key=queue.name
    )

    msg = await queue.get(timeout=5)
    assert msg.body == b"ping"
    await msg.ack()


async def test_topic_exchange_routes_by_pattern(channel):
    exchange = await channel.declare_exchange(
        f"test.{uuid.uuid4().hex}", aio_pika.ExchangeType.TOPIC, auto_delete=True
    )
    billing = await channel.declare_queue(exclusive=True)
    audit = await channel.declare_queue(exclusive=True)
    eu_only = await channel.declare_queue(exclusive=True)
    await billing.bind(exchange, routing_key="order.*")
    await audit.bind(exchange, routing_key="#")
    await eu_only.bind(exchange, routing_key="*.created.eu")

    for key in ["order.created", "order.paid", "user.created.eu", "user.deleted"]:
        await exchange.publish(aio_pika.Message(body=key.encode()), routing_key=key)

    assert await drain(billing) == ["order.created", "order.paid"]
    assert len(await drain(audit)) == 4
    assert await drain(eu_only) == ["user.created.eu"]


async def test_rejected_message_goes_to_dead_letter_queue(channel):
    dead = await channel.declare_queue(f"test.dead.{uuid.uuid4().hex}", exclusive=True)
    work = await channel.declare_queue(
        f"test.work.{uuid.uuid4().hex}",
        exclusive=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dead.name,
        },
    )

    await channel.default_exchange.publish(
        aio_pika.Message(body=b"poison"), routing_key=work.name
    )
    msg = await work.get(timeout=5)
    await msg.reject(requeue=False)  # requeue=False ← می‌ره به DLX

    dead_msg = await dead.get(timeout=5)
    assert dead_msg.body == b"poison"
    await dead_msg.ack()
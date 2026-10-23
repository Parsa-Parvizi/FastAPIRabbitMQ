import asyncio
import os

import aio_pika

from app.mq import connect_with_retry

URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")


async def add_consumer(channel, exchange, name, patterns):
    queue = await channel.declare_queue(f"lab.{name}", exclusive=True)
    for pattern in patterns:
        await queue.bind(exchange, routing_key=pattern)

    async def on_message(msg: aio_pika.IncomingMessage):
        async with msg.process():
            print(f"[{name:8}] key={msg.routing_key:16} body={msg.body.decode()}")

    await queue.consume(on_message)


async def main():
    conn = await connect_with_retry(URL)
    channel = await conn.channel()
    exchange = await channel.declare_exchange(
        "lab.events", aio_pika.ExchangeType.TOPIC, durable=True
    )

    await add_consumer(channel, exchange, "billing", ["order.*"])
    await add_consumer(channel, exchange, "audit", ["#"])
    await add_consumer(channel, exchange, "eu-only", ["*.created.eu"])

    for key in ["order.created", "order.paid", "user.created.eu", "user.deleted"]:
        await exchange.publish(aio_pika.Message(body=key.upper().encode()), routing_key=key)

    await asyncio.sleep(1)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
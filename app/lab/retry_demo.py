import asyncio
import os

import aio_pika

from app.mq import connect_with_retry

URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
MAX_ATTEMPTS = 3


async def main():
    conn = await connect_with_retry(URL)
    ch = await conn.channel()

    work = await ch.declare_queue("lab.work", durable=True)
    await ch.declare_queue(
        "lab.work.retry",
        durable=True,
        arguments={
            "x-message-ttl": 3000,                 # ۳ ثانیه صبر
            "x-dead-letter-exchange": "",          # بعدش به default exchange
            "x-dead-letter-routing-key": "lab.work",  # و برگرد به صف اصلی
        },
    )
    await ch.declare_queue("lab.work.dead", durable=True)

    async def handle(msg: aio_pika.IncomingMessage):
        attempts = int(msg.headers.get("x-attempts", 0)) + 1
        body = msg.body.decode()
        try:
            if "fail" in body:
                raise ValueError("simulated failure")
            print(f"OK    {body!r} (attempt {attempts})")
        except Exception as exc:
            target = "lab.work.retry" if attempts < MAX_ATTEMPTS else "lab.work.dead"
            print(f"FAIL  {body!r} attempt {attempts} -> {target} ({exc})")
            await ch.default_exchange.publish(
                aio_pika.Message(
                    body=msg.body,
                    headers={"x-attempts": attempts},
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=target,
            )
        await msg.ack()  # ack فقط بعد از اینکه نتیجه جایی ثبت شد

    await work.consume(handle)

    for text in ["hello", "please fail"]:
        await ch.default_exchange.publish(
            aio_pika.Message(body=text.encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key="lab.work",
        )

    await asyncio.sleep(15)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
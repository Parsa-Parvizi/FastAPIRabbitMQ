import asyncio
import logging

import aio_pika

log = logging.getLogger("mq")


async def connect_with_retry(url: str, attempts: int = 30, delay: float = 2.0):
    last_exc = None
    for i in range(1, attempts + 1):
        try:
            return await aio_pika.connect_robust(url)
        except (aio_pika.exceptions.AMQPConnectionError, OSError) as exc:
            last_exc = exc
            log.warning("RabbitMQ not ready (%d/%d): %s", i, attempts, exc)
            await asyncio.sleep(delay)
    raise RuntimeError(f"RabbitMQ unreachable at {url!r}") from last_exc
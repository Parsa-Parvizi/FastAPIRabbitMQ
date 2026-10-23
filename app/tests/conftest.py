import os
import tempfile
from pathlib import Path

# باید قبل از import کردن app.db باشه، چون engine موقع import ساخته می‌شه.
# هر اجرای تست یه دیتابیس موقت جدا می‌گیره و به دیتابیس واقعی دست نمی‌زنه.
_tmp = tempfile.mkdtemp(prefix="rabbit-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_tmp, 'test.db').as_posix()}"

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


class FakeExchange:
    def __init__(self):
        self.published = []  # [(routing_key, message), ...]

    async def publish(self, message, routing_key):
        self.published.append((routing_key, message))


class FakeChannel:
    def __init__(self):
        self.default_exchange = FakeExchange()


class FakeConnection:
    is_closed = False


@pytest_asyncio.fixture
async def db():
    await init_db()
    yield
    # connectionهای pool به event loop همون تست وصلن؛ آخر هر تست آزادشون می‌کنیم
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_channel(db):
    channel = FakeChannel()
    app.state.channel = channel
    app.state.connection = FakeConnection()
    return channel


@pytest_asyncio.fixture
async def client(fake_channel):
    # ASGITransport اجرای lifespan رو انجام نمی‌ده، پس RabbitMQ واقعی لازم نیست
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
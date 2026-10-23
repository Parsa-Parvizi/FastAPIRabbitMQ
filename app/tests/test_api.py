import json

import aio_pika

from app.main import QUEUE


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"rabbitmq": True}


async def test_create_task_saves_and_publishes(client, fake_channel):
    r = await client.post("/tasks", json={"name": "hello", "payload": {"a": 1}})

    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"

    published = fake_channel.default_exchange.published
    assert len(published) == 1
    routing_key, message = published[0]
    assert routing_key == QUEUE
    assert json.loads(message.body) == {"id": body["id"]}  # فقط id، نه کل داده
    assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT


async def test_get_task_returns_saved_task(client):
    created = (await client.post("/tasks", json={"name": "report"})).json()

    r = await client.get(f"/tasks/{created['id']}")

    assert r.status_code == 200
    assert r.json() == {"id": created["id"], "name": "report", "status": "pending"}


async def test_get_unknown_task_is_404(client):
    r = await client.get("/tasks/999999")
    assert r.status_code == 404


async def test_invalid_task_is_rejected_and_not_published(client, fake_channel):
    r = await client.post("/tasks", json={"payload": {}})  # name نداره

    assert r.status_code == 422
    assert fake_channel.default_exchange.published == []
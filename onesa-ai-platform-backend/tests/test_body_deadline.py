import asyncio

from app.limits import BodyLimit


def test_slow_body_has_total_deadline_and_never_reaches_parser():
    messages = []

    async def app(scope, receive, send):
        raise AssertionError("Timed-out body reached the parser")

    async def receive():
        await asyncio.sleep(0.05)
        return {"type": "http.request", "body": b"x", "more_body": True}

    async def send(message):
        messages.append(message)

    asyncio.run(BodyLimit(app, deadline=0.01)({"type": "http", "method": "POST"}, receive, send))
    assert messages[0]["status"] == 408
    assert b"request_timeout" in messages[1]["body"]

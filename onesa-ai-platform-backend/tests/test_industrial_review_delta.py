"""Review reproductions with synthetic fixtures and isolated PostgreSQL only."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import Request

from app import industrial
from app.config import Settings
from app.industrial_evidence import Window, calculate, coverage, fixture
from tests.test_industrial import enable, new


@pytest.mark.parametrize("quality", ["bad", "unknown"])
def test_partial_quality_abstains_before_retrieval_or_model(quality, monkeypatch):
    evidence = fixture("demo-press-01", "reference")
    evidence.events[0].quality = quality
    window = Window(start="2026-10-20T09:00:00Z", end="2026-10-20T10:00:00Z")
    facts = calculate(evidence, window)
    assert facts["known_downtime_seconds"] == 480 and not facts["downtime_complete"]

    def forbidden(*args):
        pytest.fail("Incomplete evidence must not reach retrieval/model")

    monkeypatch.setattr(industrial, "selected_references", forbidden)
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(state=SimpleNamespace(settings=Settings(model_backend="mock"))),
        }
    )
    result, generation = asyncio.run(
        industrial.explain(
            request,
            {
                "selection": window.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json"),
                "facts": facts,
                "coverage": coverage(evidence, window),
            },
        )
    )
    assert result["abstained"] and not result["hypotheses"]
    assert generation["mode"] == "not_requested_insufficient_evidence"


def test_cancel_restart_stops_old_observer_without_overwriting_new_revision(api, monkeypatch):
    enable(api)
    api.app.state.settings.model_backend = "vllm"
    api.app.state.settings.model_global_concurrency = 2
    api.app.state.settings.model_user_concurrency = 2
    first_waiting, release_old, second_stream, old_closed = (Event() for _ in range(4))
    original_wait = asyncio.wait
    calls = 0

    async def controlled_wait(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_waiting.set()
            assert await asyncio.to_thread(release_old.wait, 3)
        return await original_wait(*args, **kwargs)

    class Provider:
        streams = 0

        async def stream(self, messages):
            self.streams += 1
            index = self.streams
            if index == 2:
                second_stream.set()
            try:
                await asyncio.Event().wait()
                yield ""  # async generator, never produces model text
            finally:
                if index == 1:
                    old_closed.set()

    monkeypatch.setattr(industrial.asyncio, "wait", controlled_wait)
    api.app.state.model_client = Provider()
    row = new(api)
    path = f"/api/v1/industrial/investigations/{row['id']}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(api.post, path + "/generate", json={"expected_revision": 1})
        assert first_waiting.wait(3)
        current = api.get(path).json()
        cancelled = api.post(
            path + "/cancel", json={"expected_revision": current["revision"]}
        ).json()
        second = executor.submit(
            api.post, path + "/generate", json={"expected_revision": cancelled["revision"]}
        )
        try:
            assert second_stream.wait(3)
            restarted = api.get(path).json()
            assert restarted["status"] == "running"
            release_old.set()
            response = first.result(timeout=2)
            assert old_closed.wait(1)
            assert response.json()["revision"] == restarted["revision"]
            assert api.get(path).json()["revision"] == restarted["revision"]
        finally:
            release_old.set()
            current = api.get(path).json()
            if current["status"] == "running":
                api.post(path + "/cancel", json={"expected_revision": current["revision"]})
            first.result(timeout=4)
            second.result(timeout=4)

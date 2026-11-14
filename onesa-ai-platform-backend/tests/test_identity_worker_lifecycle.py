"""Worker lifetime boundaries; delivery/lease integration remains in test_identity."""

import signal
import sys
from threading import Event
from unittest.mock import MagicMock

import pytest

from app import identity_worker as worker
from app.config import Settings


def test_bounded_claims_and_empty_queue(monkeypatch):
    engine, client = MagicMock(), MagicMock()
    maintain, process = MagicMock(), MagicMock(return_value=True)
    monkeypatch.setattr(worker, "maintenance", maintain)
    monkeypatch.setattr(worker, "process_one", process)
    assert worker.run_worker(engine, Settings(), client, Event(), 3) == 3
    assert process.call_count == 3
    process.reset_mock()
    process.return_value = False
    assert worker.run_worker(engine, Settings(), client, Event(), 20) == 0
    assert process.call_count == 1
    with pytest.raises(ValueError):
        worker.run_worker(engine, Settings(), client, Event(), 0)


def test_stop_during_maintenance_does_not_claim(monkeypatch):
    stop, process = Event(), MagicMock()
    monkeypatch.setattr(worker, "maintenance", lambda _: stop.set())
    monkeypatch.setattr(worker, "process_one", process)
    assert worker.run_worker(MagicMock(), Settings(), MagicMock(), stop) == 0
    process.assert_not_called()


def test_sigterm_finishes_current_claim_and_closes_resources(monkeypatch):
    engine, client = MagicMock(), MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr(sys, "argv", ["identity_worker"])
    monkeypatch.setattr(worker, "Settings", lambda: Settings(database_url="postgresql://fixture"))
    monkeypatch.setattr(worker, "make_engine", lambda _: engine)
    monkeypatch.setattr(worker.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(worker, "maintenance", lambda _: None)
    previous = signal.getsignal(signal.SIGTERM)

    def claimed(*_):
        handler = signal.getsignal(signal.SIGTERM)
        handler(signal.SIGTERM, None)
        return True

    process = MagicMock(side_effect=claimed)
    monkeypatch.setattr(worker, "process_one", process)
    worker.main()
    assert process.call_count == 1
    engine.dispose.assert_called_once()
    client.__exit__.assert_called_once()
    assert signal.getsignal(signal.SIGTERM) == previous


def test_failure_still_disposes_and_restores_signals(monkeypatch):
    engine, client = MagicMock(), MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr(sys, "argv", ["identity_worker", "--once"])
    monkeypatch.setattr(worker, "Settings", lambda: Settings(database_url="postgresql://fixture"))
    monkeypatch.setattr(worker, "make_engine", lambda _: engine)
    monkeypatch.setattr(worker.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(worker, "maintenance", MagicMock(side_effect=RuntimeError("unavailable")))
    previous = signal.getsignal(signal.SIGTERM)
    with pytest.raises(RuntimeError, match="unavailable"):
        worker.main()
    engine.dispose.assert_called_once()
    client.__exit__.assert_called_once()
    assert signal.getsignal(signal.SIGTERM) == previous

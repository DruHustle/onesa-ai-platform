"""Run real integration tests on the explicitly isolated developer test database."""

import argparse
import os
from pathlib import Path

import pytest

parser = argparse.ArgumentParser()
parser.add_argument("--postgres", action="store_true")
args = parser.parse_args()
if args.postgres:
    os.environ.setdefault(
        "ONESA_TEST_DATABASE_URL",
        "postgresql+psycopg://onesa:onesa-test-only@127.0.0.1:55432/onesa_test?connect_timeout=3",
    )
os.chdir(Path(__file__).resolve().parents[1] / "onesa-ai-platform-backend")
raise SystemExit(pytest.main(["-q"]))

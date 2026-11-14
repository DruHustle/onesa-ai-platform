"""Exercise the actual Linux worker restrictions in a disposable subprocess."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "linux", reason="Linux seccomp deployment only")
def test_pdf_worker_denies_files_network_and_execution() -> None:
    source = Path(__file__).resolve().parents[1] / "app/pdf_restrictions.py"
    probe = """
import importlib.util, socket, os, errno
spec = importlib.util.spec_from_file_location("restrictions", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.restrict()
attempts = (
    lambda: open("/etc/passwd"), lambda: socket.socket(),
    lambda: os.fork(), lambda: os.execv("/bin/true", ["true"])
)
for attempt in attempts:
    try:
        attempt()
    except OSError as error:
        assert error.errno == errno.EPERM
    else:
        raise AssertionError("Restricted operation unexpectedly allowed")
print("files, sockets, fork and exec denied")
""".replace("SOURCE", repr(str(source)))
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert "files, sockets, fork and exec denied" in result.stdout

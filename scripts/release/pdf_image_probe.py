"""Run inside the native release image; no network or real file contents are accessed."""

import errno
import os
import socket
from pathlib import Path

from app.pdf_restrictions import restrict

restrict()
for operation in [
    lambda: Path("/etc/passwd").read_bytes(),
    lambda: socket.socket(),
    lambda: os.fork(),
    lambda: os.execv("/bin/true", ["true"]),
]:
    try:
        operation()
    except OSError as error:
        assert error.errno == errno.EPERM
    else:
        raise AssertionError("PDF operation was not denied")
print("PASS: file/socket/fork/exec denied by the native runtime")

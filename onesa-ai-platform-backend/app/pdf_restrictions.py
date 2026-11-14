"""Linux PDF-worker syscall reduction; this is one control, not a complete security sandbox."""

import ctypes
import errno
import platform
import sys


class Filter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("jt", ctypes.c_ubyte),
        ("jf", ctypes.c_ubyte),
        ("k", ctypes.c_uint),
    ]


class Program(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]


def restrict() -> None:
    if sys.platform != "linux":
        return
    architectures = {
        "aarch64": (
            0xC00000B7,
            [56, 437, 198, 199, 220, 435, 221, 281, 117, 270, 271, 425, 426, 427],
        ),
        "x86_64": (
            0xC000003E,
            [2, 257, 437, 41, 53, 56, 57, 58, 435, 59, 322, 101, 310, 311, 425, 426, 427],
        ),
    }
    if platform.machine() not in architectures:
        raise RuntimeError("Unqualified PDF worker architecture")
    architecture, denied = architectures[platform.machine()]
    # Validate syscall ABI, reject compatibility/x32 syscalls, then deny new files,
    # network sockets, process execution, tracing, remote memory and io_uring.
    instructions = [
        Filter(0x20, 0, 0, 4),
        Filter(0x15, 1, 0, architecture),
        Filter(0x06, 0, 0, 0x80000000),
        Filter(0x20, 0, 0, 0),
        Filter(0x35, 0, 1, 0x40000000),
        Filter(0x06, 0, 0, 0x80000000),
    ]
    for number in denied:
        instructions.extend(
            [Filter(0x15, 0, 1, number), Filter(0x06, 0, 0, 0x00050000 | errno.EPERM)]
        )
    instructions.append(Filter(0x06, 0, 0, 0x7FFF0000))
    filters = (Filter * len(instructions))(*instructions)
    program = Program(len(filters), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise RuntimeError("PDF syscall restrictions unavailable")

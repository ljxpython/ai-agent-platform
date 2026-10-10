"""Container PID 1: independent deadline, pipe draining and bounded text snapshots."""

import base64
import ctypes
import hashlib
import hmac
import json
import os
import selectors
import signal
import subprocess
import sys
import time

MAX_LOG_BYTES = 1024 * 1024
MARK = b"\n[bytes omitted]\n"
PART_BYTES = 8192


class Output:
    def __init__(self):
        self.head = bytearray()
        self.tail = bytearray()
        self.total = 0

    def add(self, chunk):
        self.total += len(chunk)
        space = MAX_LOG_BYTES // 2 - len(self.head)
        self.head.extend(chunk[:space])
        self.tail.extend(chunk[space:])
        del self.tail[: max(0, len(self.tail) - MAX_LOG_BYTES // 2)]

    def snapshot(self):
        raw = bytes(self.head + self.tail)
        omitted = max(0, self.total - len(raw))
        if omitted:
            raw = bytes(self.head) + MARK + bytes(self.tail[len(MARK) :])
            omitted = self.total - (len(raw) - len(MARK))
        # Replacing invalid UTF-8 can expand bytes, so bound again after decoding.
        text = raw.decode("utf-8", errors="replace").encode()
        if len(text) > MAX_LOG_BYTES:
            text = (
                text[: MAX_LOG_BYTES // 2 - len(MARK)]
                + MARK
                + text[-MAX_LOG_BYTES // 2 :]
            )
        text = text.decode("utf-8", errors="ignore").encode()
        return text, omitted, bool(omitted or len(text) < len(raw))

    def emit(self, sequence):
        text, omitted, truncated = self.snapshot()
        pieces = [
            text[n : n + PART_BYTES] for n in range(0, len(text), PART_BYTES)
        ] or [b""]
        for index, piece in enumerate(pieces):
            print(
                json.dumps(
                    {
                        "snapshot": sequence,
                        "part": index,
                        "parts": len(pieces),
                        "data": base64.b64encode(piece).decode(),
                        "omitted": omitted,
                        "truncated": truncated,
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )


def run(command, timeout):
    stopping = False
    secret = os.environ.pop("RUNTIME_BACKGROUND_RECEIPT_SECRET")
    # Same-UID shell children must not read the supervisor's environment or memory.
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) != 0:
        raise RuntimeError("runner isolation unavailable")

    def terminate(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    process = subprocess.Popen(
        ["/bin/sh", "-c", command],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    os.set_blocking(process.stdout.fileno(), False)
    output, sequence = Output(), 0
    started = time.monotonic()
    deadline, next_snapshot = started + timeout, started + 1
    kill_at, outcome, eof = None, None, False
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            now = time.monotonic()
            if kill_at is None and (
                stopping or now >= deadline or process.poll() is not None
            ):
                outcome = (
                    21
                    if stopping
                    else 20
                    if now >= deadline and process.poll() is None
                    else 0
                    if process.returncode == 0
                    else 1
                )
                kill_at = now + 1
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            if kill_at is not None and now >= kill_at:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if process.poll() is not None:
                    break
            for key, _ in selector.select(0.05):
                chunk = os.read(key.fd, 8192)
                if chunk:
                    output.add(chunk)
                else:
                    eof = True
                    selector.unregister(key.fileobj)
            if now >= next_snapshot:
                output.emit(sequence)
                sequence += 1
                next_snapshot = now + 5
            if process.poll() is not None and eof:
                break
    process.wait()
    output.emit(sequence)
    outcome = outcome if outcome is not None else 0 if process.returncode == 0 else 1
    receipt = {"exit_code": process.returncode, "outcome": outcome}
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        secret.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    print(
        json.dumps({"receipt": receipt, "signature": signature}, separators=(",", ":")),
        flush=True,
    )
    return outcome


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], int(sys.argv[2])))

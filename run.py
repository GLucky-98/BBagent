#!/usr/bin/env python3
"""
BBagent one-click start script
Usage: python run.py
"""
import argparse
import os
import signal
import subprocess
import sys
import time
import uvicorn

from backend.logging import get_uvicorn_log_config


def find_processes_on_port(port: int = 8000) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        return [int(pid) for pid in result.stdout.strip().split() if pid]
    except Exception:
        return []


def stop_processes(pids: list[int], timeout: float = 3.0):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to process PID={pid}")
        except ProcessLookupError:
            pass

    deadline = time.time() + timeout
    remaining = list(pids)
    while remaining and time.time() < deadline:
        remaining = [pid for pid in remaining if _is_running(pid)]
        if remaining:
            time.sleep(0.1)

    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"Sent SIGKILL to process PID={pid}")
        except ProcessLookupError:
            pass


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def main():
    parser = argparse.ArgumentParser(description="Start the BBagent API server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Terminate processes already listening on the selected port before starting.",
    )
    args = parser.parse_args()

    pids = find_processes_on_port(args.port)
    if pids and not args.kill_existing:
        joined = ", ".join(str(pid) for pid in pids)
        print(
            f"Port {args.port} is already in use by PID(s): {joined}.\n"
            f"Stop them yourself, choose another port with --port, or rerun with --kill-existing.",
            file=sys.stderr,
        )
        sys.exit(1)
    if pids:
        stop_processes(pids)

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=True,
        reload_dirs=["backend"],
        log_config=get_uvicorn_log_config(),
    )


if __name__ == "__main__":
    main()

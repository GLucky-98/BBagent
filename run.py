#!/usr/bin/env python3
"""
BBagent 一键启动脚本
用法: python run.py
"""
import os
import signal
import subprocess
import sys
import uvicorn


def kill_old_server(port: int = 8000):
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(pid) for pid in result.stdout.strip().split() if pid]
        for pid in pids:
            os.kill(pid, signal.SIGKILL)
            print(f"Killed old process PID={pid} on port {port}")
    except Exception:
        pass


def main():
    kill_old_server(8000)
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["backend"],
    )


if __name__ == "__main__":
    main()
